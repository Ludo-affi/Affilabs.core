# Spark AI - Manual Injection & Method Execution Guide

**Date:** February 14, 2026
**Training Type:** Pattern Matching (Fast Path)
**Knowledge Domain:** P4SPR Manual Injection Workflow

---

## Overview

This guide explains how manual injection works with the P4SPR system, including method building, cycle execution, and the intelligent injection detection system.

### What is Manual Injection?

**Manual injection** is when you physically inject your sample using a syringe instead of using automated pumps. The Affilabs.core software automatically detects the injection in real-time and places markers on the sensorgram.

**When to Use:**
- P4SPR systems without AffiPump hardware
- Quick single injections without pump setup
- Binding cycles where you manually change samples
- Training/teaching demonstrations

**Advantages:**
- No pump hardware required
- Faster setup for simple experiments
- More control over injection technique
- Works with any sample volume/concentration

---

## Method Building Basics

### What is a Method?

A **Method** is a sequence of **Cycles** that defines your entire experiment. Think of it like a recipe:

```
Method = "Binding Study 1"
├── Cycle 1: Baseline (5 min)
├── Cycle 2: Association - Sample A (10 min) ← INJECTION HERE
├── Cycle 3: Dissociation (5 min)
├── Cycle 4: Regeneration (2 min)
└── Cycle 5: Baseline (3 min)
```

### Cycle Types

| Type | Purpose | Typical Duration | Requires Injection? |
|------|---------|------------------|---------------------|
| **Baseline** | Establish stable baseline signal | 3-10 min | ❌ No |
| **Association** | Sample binding phase | 5-15 min | ✅ **YES** (manual or auto) |
| **Dissociation** | Watch sample unbind | 5-30 min | ❌ No |
| **Regeneration** | Strip surface for reuse | 1-3 min | ✅ Yes (usually automated) |
| **Wash** | Clean sensor/tubing | 1-5 min | ❌ No |
| **Concentration** | Multi-injection titration | Varies | ✅ **YES** (multiple) |
| **Immobilization** | Attach ligand to surface | 5-15 min | ✅ Yes |
| **Blocking** | Block unused surface | 2-10 min | ✅ Yes |

### Building a Method

**Location:** Main window → **Method** tab (left sidebar)

1. **Click "Add Cycle"** - Opens cycle builder dialog
2. **Select cycle type** from dropdown (Baseline, Association, etc.)
3. **Set duration** in minutes (e.g., 5.0)
4. **Name your cycle** (e.g., "100nM HSA" or "Baseline 1")
5. **Add notes** (optional) - concentration, sample ID, etc.
6. **Set flow rate** - typically 50-100 µL/min for P4SPR
7. **Click "Add"** - cycle appears in queue

**Pro Tips:**
- Always start with a **Baseline** cycle (3-5 min) to stabilize signal
- End with another **Baseline** to see if regeneration worked
- Use descriptive names: "100nM HSA" instead of "Association 1"
- Put concentration in the name for easy identification

---

## Manual Injection Workflow

### Step-by-Step: Running Your First Manual Injection

#### 1. Prepare Your Method
```
Build queue:
├── Baseline (5 min)
├── Association - 100nM Sample (10 min)  ← Your injection cycle
└── Dissociation (5 min)
```

#### 2. Start the Method
- Click **"Start Method"** button
- System begins running **Cycle 1: Baseline**
- Buffer flows at set rate (e.g., 100 µL/min)
- Sensorgram shows stable baseline

#### 3. When It's Time to Inject

**What Happens Automatically:**
- Affilabs.core finishes the Baseline cycle
- Starts **Association** cycle
- **Injection prompt appears** (unified cycle bar turns green with "INJECT" state)
- **60-second countdown timer** starts automatically
- System monitors all 4 channels (A/B/C/D) for injection signal

**What You See:**
```
┌─────────────────────────────────────────────┐
│ 💉 Manual Injection                         │
│                                              │
│ Sample: 100nM HSA                           │
│ 🔍 Monitoring for injection... ✓ 1:00      │
│                                              │
│ [Cancel]              [✓ Done Injecting]   │
└─────────────────────────────────────────────┘
```

#### 4. Perform Your Injection

**Injection Technique:**
1. Prepare syringe with 50-100 µL sample
2. Connect to injection port (typically port 5 on 6-port valve)
3. **Inject smoothly over 5-10 seconds** (slow, steady push)
4. Wait 2-3 seconds for signal to rise
5. Click **"✓ Done Injecting"** button

**Important Notes:**
- ⏱️ You have **60 seconds total** to inject (timer shows remaining time)
- 🔍 System detects injection **automatically** while you inject
- ✅ Click "Done Injecting" when you're finished (don't wait for timer to expire)
- 🎯 System continues monitoring for 10 more seconds after you click "Done"
- ⚠️ If no injection detected in 60 seconds, cycle continues anyway

#### 5. Automatic Injection Detection

**What the System Does:**
- **Scans all 4 channels** (A → B → C → D) every 200ms
- **Looks for signal jumps** characteristic of sample injection
- **ML-powered detection** with 70% confidence threshold
- **Places injection marker** automatically when detected
- **Validates across channels** to avoid false positives

**Detection Indicators:**
```
Channel A: ✓ Injection detected at 5.2 min (confidence: 85%)
Channel B: ✓ Injection detected at 5.2 min (confidence: 92%)
Channel C: ✓ Injection detected at 5.3 min (confidence: 78%)
Channel D: ✓ Injection detected at 5.2 min (confidence: 88%)
```

#### 6. Injection Confirmed

**What Happens Next:**
- ✅ **Orange vertical line** appears on sensorgram (injection marker)
- ✅ Status updates: "Injection detected at 5.2 min"
- ✅ Dialog closes automatically or you click "Done Injecting"
- ✅ System calculates **contact time** from injection point
- ✅ **Orange deadline marker** appears (injection time + contact time)
- ✅ Association cycle continues running
- ✅ Data collection proceeds normally

#### 7. Cycle Completes

- Association cycle runs for full duration (e.g., 10 min)
- System automatically advances to next cycle (Dissociation)
- Your injection data is saved with precise timing
- Sensorgram shows binding curve

---

## Advanced Features

### Binding Cycles (Multi-Injection)

**What is a Binding Cycle?**
A single cycle with **multiple sequential injections** at different concentrations. Perfect for dose-response curves.

**How It Works:**
1. Build ONE binding cycle (e.g., 30 min total)
2. Click **"Schedule Injections"** button
3. Enter injection times (e.g., every 5 min: 5, 10, 15, 20, 25)
4. Specify concentrations for each injection

**Example Schedule:**
```
Binding Cycle: 30 minutes
├── Injection 1 at 5 min:  10 nM  HSA
├── Injection 2 at 10 min: 50 nM  HSA
├── Injection 3 at 15 min: 100 nM HSA
├── Injection 4 at 20 min: 500 nM HSA
└── Injection 5 at 25 min: 1 µM   HSA
```

**During Execution:**
- Timer counts down to each injection point
- Prompt shows: "💉 Injection 2 of 5 • 50 nM HSA"
- You inject at each scheduled time
- System detects each injection independently
- All markers placed automatically

**Benefits:**
- Run full dose-response in one method
- No need to stop/restart between injections
- All data in single sensorgram
- Perfect for kinetic analysis

### Injection Detection Settings

**Confidence Threshold:** 70% (default)
- Higher = fewer false positives, may miss weak signals
- Lower = catches all injections, more false alarms
- **Best practice:** Keep at 70% unless you have issues

**Multi-Channel Detection:**
- System checks ALL 4 channels (A, B, C, D)
- Uses **highest confidence channel** for primary marker
- Validates injection across multiple channels
- Reduces false positives from noise spikes

**Scan Strategy:**
```
Channel priority: A → B → C → D
1. Check Channel A first (usually most active)
2. If >70% confidence → mark injection
3. Otherwise check B, C, D in sequence
4. Use best channel for marker placement
```

### Contact Time Tracking

**What is Contact Time?**
The duration your sample is in contact with the sensor surface.

**How It Works:**
1. You inject at time = 5.2 min (detected automatically)
2. Cycle continues for 10 min total
3. **Contact time = 10 - 5.2 = 4.8 min**
4. Orange **deadline marker** appears at injection + contact time
5. This helps you see exactly how long sample was present

**Why It Matters:**
- Critical for kinetic analysis (association rate calculation)
- Ensures consistent contact time across replicates
- Helps troubleshoot binding issues (too short = low signal)

### Wash Deadline Markers

**Auto-Enabled for Manual Injection Cycles**

- System automatically places **orange vertical line** at end of contact time
- Shows when sample contact ends (wash will occur after this point)
- Helps align analysis regions
- Visible on live sensorgram and exported data

---

## Troubleshooting

### Injection Not Detected

**Symptoms:**
- Timer expires at 60 seconds
- No orange injection marker appears
- Status shows "No injection detected"

**Causes & Fixes:**

1. **Injection too slow/small**
   - ✅ Inject 50-100 µL quickly (5-10 seconds)
   - ✅ Use larger injection volume
   - ✅ Ensure syringe fully pushes sample

2. **Wrong injection port**
   - ✅ Check valve configuration (usually port 5)
   - ✅ Verify tubing connections
   - ✅ Ensure valve is in correct position

3. **Sample very similar to buffer**
   - ✅ Use higher contrast sample
   - ✅ Check refractive index difference
   - ✅ Add more protein/analyte

4. **Noisy baseline**
   - ✅ Run longer baseline first (5+ min)
   - ✅ Check for air bubbles in tubing
   - ✅ Verify stable temperature

**Manual Override:**
If detection fails, you can manually place injection marker:
- Right-click on sensorgram at injection time
- Select "Add Injection Flag"
- System will use this for contact time calculation

### Multiple False Detections

**Symptoms:**
- System detects injection when you haven't injected yet
- Multiple markers appear
- Detects on inactive channels

**Causes & Fixes:**

1. **Air bubble passed sensor**
   - ✅ Prime system thoroughly before starting
   - ✅ Check for leaks in tubing
   - ✅ Degas buffers

2. **Confidence threshold too low**
   - ✅ Increase to 80-85% in settings
   - ✅ Only use lower threshold if absolutely necessary

3. **Pressure spike/flow irregularity**
   - ✅ Check pump operation
   - ✅ Verify consistent flow rate
   - ✅ Look for blockages

**Prevention:**
- Run 5-minute baseline before injection cycles
- Ensure stable flow before adding injection cycles
- Monitor all 4 channels for consistent signals

### Timer Runs Out Before I Can Inject

**Symptoms:**
- Need more than 60 seconds to prepare
- Dialog closes before injection ready

**Solution:**
The 60-second window is designed to be ample time. Here's how to stay within it:

1. **Prepare BEFORE cycle starts:**
   - Fill syringe during baseline cycle
   - Connect to injection port (don't inject yet)
   - Be ready when dialog appears

2. **Request longer baseline:**
   - Add a longer baseline cycle before injection
   - This gives you more prep time

3. **Use injection schedule:**
   - For binding cycles, schedule injection 5+ min into cycle
   - Dialog only appears when injection is due

**Design Note:** 60 seconds is intentionally tight to ensure injections happen within the planned cycle window. Prepare in advance!

### Injection on Wrong Channel

**Symptoms:**
- Detection flags Channel C, but you're using Channel A
- Marker appears but on unexpected channel

**Explanation:**
- P4SPR has **4 independent channels** (A, B, C, D)
- Each can have different samples/surfaces
- System detects on **all active channels**

**What to Check:**
1. Which channels are you actually using?
2. Did you inject into correct flow path?
3. Is valve routing sample to intended channels?

**Channel Selection:**
- By default, system monitors **all 4 channels** (ABCD)
- You can specify which to monitor: `channels="AC"` for A and C only
- Use cycle **notes** to document which channels are active

---

## Method Templates

### Quick Start: Simple Binding Study

```
Method: "Simple Binding"
├── 1. Baseline (5 min, 100 µL/min)
├── 2. Association - 100nM Sample (10 min, 100 µL/min) [INJECT]
├── 3. Dissociation (10 min, 100 µL/min)
└── 4. Baseline (3 min, 100 µL/min)

Total: 28 minutes
Injections: 1 manual
```

### Multi-Sample Screening

```
Method: "4-Sample Screen"
├── 1. Baseline (5 min)
├── 2. Association - Sample A (8 min) [INJECT]
├── 3. Dissociation (5 min)
├── 4. Regeneration (2 min)
├── 5. Baseline (3 min)
├── 6. Association - Sample B (8 min) [INJECT]
├── 7. Dissociation (5 min)
├── 8. Regeneration (2 min)
├── 9. Baseline (3 min)
├── 10. Association - Sample C (8 min) [INJECT]
│   ... (repeat for Sample D)

Total: ~100 minutes
Injections: 4 manual (one per sample)
```

### Concentration Series (Dose-Response)

```
Method: "HSA Titration"
├── 1. Baseline (5 min)
└── 2. Binding Cycle (30 min)
    ├── Injection 1: 10 nM   @ 5 min [INJECT]
    ├── Injection 2: 50 nM   @ 10 min [INJECT]
    ├── Injection 3: 100 nM  @ 15 min [INJECT]
    ├── Injection 4: 500 nM  @ 20 min [INJECT]
    └── Injection 5: 1 µM    @ 25 min [INJECT]

Total: 35 minutes
Injections: 5 manual (scheduled)
```

### Regeneration Optimization

```
Method: "Test Regeneration Conditions"
├── 1. Baseline (5 min)
├── 2. Association - Test Sample (5 min) [INJECT]
├── 3. Dissociation (3 min)
├── 4. Regeneration - 10mM Glycine pH 2.0 (2 min) [INJECT]
├── 5. Baseline (5 min) ← Check if baseline recovers
├── 6. Association - Test Sample (5 min) [INJECT] ← Repeat binding
├── 7. Dissociation (3 min)
├── 8. Regeneration - 10mM Glycine pH 1.5 (2 min) [INJECT]
└── 9. Baseline (5 min) ← Compare recovery

Total: 35 minutes
Test: Compare baseline recovery after different regen conditions
```

---

## Best Practices

### Before Starting

✅ **System Preparation:**
- Run 10-minute buffer flow to stabilize baseline
- Check all 4 channels show stable signals
- Prime injection port (inject buffer to clear air)
- Verify temperature is stable (if temp control active)
- Degas buffers to prevent bubbles

✅ **Sample Preparation:**
- Prepare all samples before starting method
- Fill syringes in advance (label them!)
- Keep samples on ice or at 4°C
- Calculate needed volumes (50-100 µL per injection)
- Have extra sample ready in case of issues

✅ **Method Design:**
- Always start with Baseline cycle (5+ min)
- Use realistic cycle durations (don't rush)
- Name cycles descriptively ("100nM HSA" not "Sample 1")
- Add notes with important details (batch number, prep date)
- Set consistent flow rates (100 µL/min is standard)

### During Injection

✅ **Injection Technique:**
- Inject smoothly over 5-10 seconds (not instant)
- Push until you feel resistance stop
- Wait 2-3 seconds before clicking "Done Injecting"
- Don't remove syringe until dialog closes
- Watch sensorgram for signal rise

✅ **Timing:**
- Be ready when timer starts (syringe filled, connected)
- Don't wait for timer to run out - click "Done" when finished
- For binding cycles, inject as soon as prompt appears
- Allow 10-second detection window after clicking "Done"

### After Injection

✅ **Verify Detection:**
- Check orange injection marker appeared
- Verify marker is on correct channel(s)
- Confirm marker timing matches your injection
- Look for orange deadline marker (contact time end)

✅ **Monitor Signal:**
- Watch for signal rise (association curve)
- Check all active channels show binding
- Look for consistent shape across channels
- Note any unusual spikes or noise

✅ **Data Quality:**
- Verify baseline is stable before and after
- Check for air bubbles (sharp spikes)
- Ensure signal returns to baseline after dissociation
- Review regeneration effectiveness

---

## Technical Details

### Detection Algorithm

**How It Works:**
1. **Baseline Sampling** (before injection window)
   - Captures last 30 seconds of signal
   - Calculates baseline mean and noise level
   - Sets detection threshold = baseline + 3× noise

2. **Real-Time Scanning** (during 60-second window)
   - Samples signal every 200ms
   - Compares to baseline threshold
   - Looks for sustained rise (not just spike)

3. **Multi-Channel Validation**
   - Checks all 4 channels independently
   - Requires 70% confidence minimum
   - Uses highest confidence channel for primary marker
   - Validates timing consistency across channels

4. **Peak Confirmation**
   - Confirms signal rise persists for >2 seconds
   - Rejects single-point noise spikes
   - Filters out flow artifacts
   - ML model validates injection shape

**Confidence Scoring:**
```
Confidence = (signal_rise / noise_level) × shape_match × consistency

Where:
- signal_rise: How much signal increased (RU)
- noise_level: Baseline variability (std dev)
- shape_match: How well rise matches injection template (0-1)
- consistency: Multi-channel agreement (0-1)
```

### File Storage

**Injection Data Saved:**
- `injection_time_by_channel`: Dict of detection times per channel
- `injection_confidence_by_channel`: Dict of confidence scores
- `injection_mislabel_flags`: Warnings for unexpected channels

**Location:**
- Stored in cycle metadata (JSON)
- Exported with sensorgram data
- Available in analysis tab
- Included in Excel exports

**Example:**
```json
{
  "cycle_num": 2,
  "type": "Association",
  "name": "100nM HSA",
  "injection_time_by_channel": {
    "A": 5.23,
    "B": 5.24,
    "C": 5.22,
    "D": 5.25
  },
  "injection_confidence_by_channel": {
    "A": 0.87,
    "B": 0.92,
    "C": 0.78,
    "D": 0.88
  },
  "sensorgram_time": 0.0,
  "end_time_sensorgram": 600.0
}
```

---

## Comparison: Manual vs Automated Injection

| Feature | Manual Injection | Automated (AffiPump) |
|---------|------------------|----------------------|
| **Hardware** | Syringe + P4SPR | AffiPump + P4SPR |
| **Setup Time** | Instant | 5-10 min (prime pumps) |
| **Precision** | ±5-10 µL | ±0.1 µL |
| **Reproducibility** | User-dependent | Excellent |
| **Speed** | One injection at a time | Unlimited (automated) |
| **Flexibility** | Very flexible | Requires planning |
| **Cost** | $0 (included) | $$$$ (hardware) |
| **Best For** | Quick tests, teaching | High-throughput, kinetics |
| **Learning Curve** | Easy | Moderate |

**When to Use Manual:**
- P4SPR without pump hardware
- Single injections or small studies
- Teaching/training scenarios
- Irregular injection schedules
- Quick feasibility tests

**When to Use Automated:**
- Large screening studies (>20 samples)
- Precise kinetic measurements
- Overnight experiments
- Reproducibility critical
- Multi-cycle automation

---

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Start Method | `Ctrl+R` |
| Stop Method | `Ctrl+S` |
| Add Cycle | `Ctrl+A` |
| Clear Queue | `Ctrl+Shift+C` |
| Done Injecting | `Enter` (when dialog open) |
| Cancel Injection | `Esc` (when dialog open) |

---

## FAQ

### Q: Can I use automated pump for some cycles and manual for others?

**A:** Yes! Each cycle can specify `manual_injection_mode`:
- Set to `"manual"` for syringe injection
- Set to `"automated"` for pump injection
- Leave blank for auto-detection based on hardware

Example:
```
Cycle 1: Association (automated via pump)
Cycle 2: Regeneration (manual via syringe)
Cycle 3: Association (automated via pump)
```

### Q: What happens if I don't inject during the 60-second window?

**A:** The dialog closes and the cycle continues normally. No injection marker is placed. The association phase still runs for its full duration, but no injection time is recorded.

### Q: Can I cancel an injection after starting?

**A:** Yes, click the "Cancel" button. The cycle will STOP immediately (not continue). This allows you to abort if something goes wrong.

### Q: Why does detection sometimes miss my injection?

**Most common causes:**
1. Injection too slow (takes >15 seconds)
2. Sample very similar to buffer (low refractive index difference)
3. Noisy baseline (air bubbles, unstable flow)
4. Wrong injection port (not reaching sensor)

**Fix:** Inject faster (5-10 sec), use higher concentration, ensure stable baseline first.

### Q: Can I manually place the injection marker if auto-detection fails?

**A:** Yes! Right-click on the sensorgram at the injection time and select "Add Injection Flag". The system will use this for contact time calculations.

### Q: How do I know which channel detected the injection?

**A:** Check the status message after detection. It shows: "✓ Channel A: Injection detected at 5.2 min (confidence: 85%)". The system reports all channels that detected the injection.

### Q: What if I need more than 60 seconds?

**A:** Prepare your syringe BEFORE the injection cycle starts (during baseline). The 60-second window is designed to be used for the actual injection only, not preparation.

### Q: Can I change the confidence threshold?

**A:** Yes, but it's not recommended. The 70% threshold is optimized for P4SPR systems. Higher values may miss valid injections; lower values increase false positives.

---

## Related Documentation

- **[PUMP_TRAINING.md](PUMP_TRAINING.md)** - AffiPump automated injection guide
- **[CALIBRATION_TRAINING.md](CALIBRATION_TRAINING.md)** - System calibration procedures
- **[docs/PUMP_VALVE_SYSTEM.md](docs/PUMP_VALVE_SYSTEM.md)** - Complete pump & valve reference
- **[CYCLE_RECREATION_GUIDE.md](CYCLE_RECREATION_GUIDE.md)** - Advanced cycle design

---

## Support

**Common Issues:**
- Injection not detected → Check injection technique, baseline stability
- False detections → Verify no air bubbles, increase confidence threshold
- Timer too short → Prepare samples before cycle starts
- Wrong channel → Check valve routing, verify channel selection

**Need Help?**
- Ask Spark: Type your question in the help widget (bottom right)
- Check logs: `logs/` directory for detailed detection info
- Contact support: Include sensorgram screenshot and cycle details

---

**Last Updated:** February 14, 2026
**Software Version:** Affilabs.core v2.0+
**Hardware:** P4SPR with optional AffiPump
