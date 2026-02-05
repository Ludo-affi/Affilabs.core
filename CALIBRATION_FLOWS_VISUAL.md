# Calibration Flows - Visual Flowcharts

## 1. SIMPLE LED CALIBRATION

```
┌─────────────────────────────────────────────────────┐
│  Button Click: "Simple LED Calibration"            │
└────────────────┬────────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────────┐
│  Check Hardware Connected                           │
│  ✓ Controller + USB connected?                      │
└────────┬───────────────────────┬────────────────────┘
         │ NO                     │ YES
         v                        v
    ┌─────────┐          ┌──────────────────────┐
    │ Error   │          │ Show Progress Dialog │
    │ Dialog  │          │ (NO Start Button)    │
    └─────────┘          │ AUTO-START           │
                         └──────────┬───────────┘
                                    │
                                    v
                         ┌──────────────────────┐
                         │ Run in Thread:       │
                         │ 1. Load LED settings │
                         │ 2. S-mode measure    │
                         │ 3. Proportional adj. │
                         │ 4. P-mode measure    │
                         │ 5. Save config       │
                         │ (~10-20 seconds)     │
                         └──────────┬───────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │ SUCCESS                       │ FAILURE
                    v                               v
        ┌────────────────────────┐      ┌──────────────────────┐
        │ ✅ Complete!           │      │ ❌ Failed!           │
        │ Clear graphs (t=0)     │      │ Show error in dialog │
        │ Auto-close (2 sec)     │      │ Auto-close (3 sec)   │
        │ ❌ NO live data resume │      │ ❌ NO live data      │
        └────────────────────────┘      └──────────────────────┘
```

---

## 2. FULL CALIBRATION

```
┌─────────────────────────────────────────────────────┐
│  Button Click: "Full Calibration"                  │
└────────────────┬────────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────────┐
│  CalibrationService.start_calibration()             │
│  ✅ STOP live data acquisition                      │
│  Set: _running = False                              │
│       _calibration_completed = False                │
└────────────────┬────────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────────┐
│  Show Dialog with Checklist:                        │
│  ✓ Prism installed                                  │
│  ✓ Water/buffer applied                             │
│  ✓ No air bubbles                                   │
│  ✓ Temperature stable                               │
│  [Start Button] ← USER MUST CLICK                   │
└────────────────┬────────────────────────────────────┘
                 │ User clicks Start
                 v
┌─────────────────────────────────────────────────────┐
│  Hide Start Button, Show Progress Bar               │
│  Set: _running = True                               │
│  Start Thread: _run_calibration()                   │
└────────────────┬────────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────────┐
│  6-Step Calibration Process:                        │
│  1. Hardware validation (5%)                        │
│  2. Wavelength calibration (20%)                    │
│  3. LED model load (40%)                            │
│  4. S-mode convergence + ref (60%)                  │
│  5. P-mode convergence + ref + dark (80%)           │
│  6. QC validation (100%)                            │
│  (~30-60 sec, or ~2 min with pump)                  │
└────────────────┬────────────────────────────────────┘
                 │
    ┌────────────┴────────────┐
    │ SUCCESS                 │ FAILURE
    v                         v
┌────────────────────┐   ┌──────────────────────┐
│ Set flags:         │   │ Emit:                │
│ _completed = True  │   │ calibration_failed   │
│ Emit: complete     │   │ Update dialog:       │
│                    │   │ [ERROR] Failed       │
│ Update dialog:     │   │ Hide progress bar    │
│ ✅ Successful!     │   │                      │
│ Enable Start btn   │   │ Reset:               │
│ (for live view)    │   │ _running = False     │
└─────────┬──────────┘   └──────────────────────┘
          │
          v
┌─────────────────────────────────────────────────────┐
│  Application Handler (_on_calibration_complete):    │
│  1. Set LED intensities                             │
│  2. Show QC Dialog (modal)                          │
│  3. Log to database                                 │
│  4. Clear graphs                                    │
│  5. ✅ Resume live acquisition                      │
└─────────────────────────────────────────────────────┘
```

---

## 3. POLARIZER CALIBRATION

```
┌─────────────────────────────────────────────────────┐
│  Button Click: "Calibrate Polarizer (Servo)"       │
└────────────────┬────────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────────┐
│  Check Hardware Connected                           │
│  ✓ Controller + USB connected?                      │
└────────┬───────────────────────┬────────────────────┘
         │ NO                     │ YES
         v                        v
    ┌─────────┐          ┌──────────────────────┐
    │ Error   │          │ ✅ STOP live data    │
    │ Dialog  │          │ acquisition          │
    └─────────┘          └──────────┬───────────┘
                                    │
                                    v
                         ┌──────────────────────┐
                         │ Show QProgressDialog │
                         │ "Initializing..."    │
                         │ [Cancel Button]      │
                         └──────────┬───────────┘
                                    │
                                    v
                         ┌──────────────────────┐
                         │ Import & Run:        │
                         │ run_calibration_     │
                         │ with_hardware()      │
                         │                      │
                         │ 1. Sweep servo       │
                         │ 2. Find S/P windows  │
                         │ 3. Save positions    │
                         │ (~2-5 minutes)       │
                         └──────────┬───────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │ SUCCESS                       │ FAILURE
                    v                               v
        ┌────────────────────────┐      ┌──────────────────────┐
        │ Close dialog           │      │ Close dialog         │
        │ Load servo positions   │      │ Log error            │
        │ ✅ Resume live data    │      │ Show error dialog    │
        │ Show success dialog:   │      │ ❌ NO live resume    │
        │ "Calibration Complete" │      └──────────────────────┘
        │ ❌ NO graph clear      │
        └────────────────────────┘
```

---

## 4. OEM CALIBRATION

```
┌─────────────────────────────────────────────────────┐
│  Button Click: "Run OEM Calibration"               │
└────────────────┬────────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────────┐
│  Show Dialog with Process Overview:                 │
│  STEP 1: Servo calibration (~2-5 min)               │
│  STEP 2: LED model training (~2 min)                │
│  STEP 3: Full 6-step calibration (~3-5 min)         │
│  Total: ~10-15 minutes                              │
│  [Start Button] ← USER MUST CLICK                   │
└────────────────┬────────────────────────────────────┘
                 │ User clicks Start
                 v
┌─────────────────────────────────────────────────────┐
│  Disable Start Button                               │
│  Show Progress Bar                                  │
│  Set: _force_oem_retrain = True                     │
│       _calibration_dialog = dialog                  │
│       _running = True                               │
│  Start calibration thread                           │
└────────────────┬────────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────────┐
│  PHASE 1: Servo Polarizer Calibration               │
│  - Detect polarizer type                            │
│  - Sweep positions                                  │
│  - Save S/P positions                               │
│  (~2-5 minutes)                                     │
└────────────────┬────────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────────┐
│  PHASE 2: LED Model Training                        │
│  - Measure LED response [10-60ms]                   │
│  - Fit 3-stage linear models                        │
│  - Save model file                                  │
│  (~2 minutes)                                       │
└────────────────┬────────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────────┐
│  PHASE 3: Full 6-Step Calibration                   │
│  - Use newly trained model                          │
│  - LED convergence S + P                            │
│  - Reference capture                                │
│  (~3-5 minutes)                                     │
└────────────────┬────────────────────────────────────┘
                 │
    ┌────────────┴────────────┐
    │ SUCCESS                 │ FAILURE
    v                         v
┌────────────────────┐   ┌──────────────────────┐
│ SAME AS FULL CAL:  │   │ SAME AS FULL CAL:    │
│ - Show QC dialog   │   │ - Show error dialog  │
│ - Clear graphs     │   │ - NO graph clear     │
│ - ✅ Resume live   │   │ - ❌ NO live resume  │
│ - Set intensities  │   └──────────────────────┘
└────────────────────┘
```

---

## 5. TRAIN LED MODEL

```
┌─────────────────────────────────────────────────────┐
│  Button Click: "Train LED Model"                   │
└────────────────┬────────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────────┐
│  Check Hardware Connected                           │
│  ✓ Controller + USB connected?                      │
└────────┬───────────────────────┬────────────────────┘
         │ NO                     │ YES
         v                        v
    ┌─────────┐          ┌──────────────────────┐
    │ Error   │          │ Show Dialog:         │
    │ Dialog  │          │ Training process     │
    └─────────┘          │ (~2-5 minutes)       │
                         │ [Start Button]       │
                         └──────────┬───────────┘
                                    │ User clicks Start
                                    v
                         ┌──────────────────────┐
                         │ Disable Start Button │
                         │ Show Progress Bar    │
                         │ Start Thread         │
                         └──────────┬───────────┘
                                    │
                                    v
                         ┌──────────────────────┐
                         │ Step 1: Servo Cal    │
                         │ (if P4SPR device)    │
                         └──────────┬───────────┘
                                    │
                                    v
                         ┌──────────────────────┐
                         │ Step 2: Measure      │
                         │ Dark current         │
                         └──────────┬───────────┘
                                    │
                                    v
                         ┌──────────────────────┐
                         │ Step 3: For each LED │
                         │ Test [30,60,90,      │
                         │ 120,150] intensities │
                         │ at [10,20,30,45,60]ms│
                         └──────────┬───────────┘
                                    │
                                    v
                         ┌──────────────────────┐
                         │ Step 4: Fit linear   │
                         │ models (3-stage)     │
                         └──────────┬───────────┘
                                    │
                                    v
                         ┌──────────────────────┐
                         │ Step 5: Save model   │
                         │ to file              │
                         └──────────┬───────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │ SUCCESS                       │ FAILURE
                    v                               v
        ┌────────────────────────┐      ┌──────────────────────┐
        │ Update dialog:         │      │ Update dialog:       │
        │ "Training Complete"    │      │ "Training Failed"    │
        │ Hide progress bar      │      │ Hide progress bar    │
        │                        │      │                      │
        │ Close dialog (500ms)   │      │ Close dialog (500ms) │
        │ Show info dialog:      │      │ Show error dialog    │
        │ "Model created!"       │      │ "Training failed"    │
        │ ❌ NO graph clear      │      │ ❌ NO graph clear    │
        │ ❌ NO live resume      │      │ ❌ NO live resume    │
        └────────────────────────┘      └──────────────────────┘
```

---

## STATE MACHINE DIAGRAM - Full Calibration

```
                    [IDLE]
                      │
                      │ Button Click
                      v
              ┌─────────────┐
              │ STOPPING    │
              │ LIVE DATA   │
              └──────┬──────┘
                     │
                     v
              ┌─────────────┐
              │ SHOWING     │
              │ CHECKLIST   │
              └──────┬──────┘
                     │ User clicks Start
                     v
              ┌─────────────┐
              │ CALIBRATING │
              │ _running=T  │
              └──────┬──────┘
                     │
        ┌────────────┴────────────┐
        │                         │
        v                         v
  [SUCCESS]                  [FAILURE]
  _completed=T               _completed=F
        │                         │
        v                         v
  ┌──────────┐             ┌──────────┐
  │ SHOWING  │             │ SHOWING  │
  │ QC       │             │ ERROR    │
  │ DIALOG   │             │ DIALOG   │
  └────┬─────┘             └────┬─────┘
       │                        │
       v                        v
  ┌──────────┐             ┌──────────┐
  │ RESUMING │             │ IDLE     │
  │ LIVE     │             │ _running=F│
  └────┬─────┘             └──────────┘
       │
       v
  ┌──────────┐
  │ IDLE     │
  │ _running=F│
  └──────────┘
```

---

## COMPARISON: Auto-Start vs Manual Start

### AUTO-START (Immediate Execution)
```
Button Click → Check Hardware → Show Dialog → START IMMEDIATELY
                                  (no button)
Examples: Simple LED, Polarizer
Pros: Fast, no extra step
Cons: Can't review requirements first
```

### MANUAL START (User Confirmation Required)
```
Button Click → Show Checklist → USER CLICKS START → Begin Calibration
               (requirements)      (deliberate action)
Examples: Full Calibration, OEM Calibration, LED Training
Pros: User reviews requirements, deliberate action
Cons: Extra click required
```

---

## LIVE DATA FLOW COMPARISON

### TYPE A: Stops → Auto-Resumes
```
Full Calibration, OEM Calibration, Polarizer Calibration

Entry: ✅ data_mgr.stop_acquisition()
Exit:  ✅ data_mgr.start_acquisition() (on success)
```

### TYPE B: No Stop → No Resume
```
Simple LED Calibration, LED Model Training

Entry: ❌ No stop (assumes not running)
Exit:  ❌ No resume
Issue: May conflict with live data if running
```

---

## RECOMMENDED UNIFIED PATTERN

```
┌─────────────────────────────────────────────────────┐
│  ANY CALIBRATION BUTTON CLICKED                     │
└────────────────┬────────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────────┐
│  1. Check if calibration already running            │
│     if _running: show warning, return               │
└────────────────┬────────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────────┐
│  2. Check hardware connected                        │
│     if not connected: show error, return            │
└────────────────┬────────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────────┐
│  3. STOP live data acquisition                      │
│     if data_mgr._acquiring: stop()                  │
└────────────────┬────────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────────┐
│  4. Show dialog with:                               │
│     - Requirements checklist                        │
│     - Process description                           │
│     - Duration estimate                             │
│     - Start button (for long operations)            │
│       OR auto-start (for quick operations <30 sec)  │
└────────────────┬────────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────────┐
│  5. Set state flags:                                │
│     _running = True                                 │
│     _calibration_completed = False                  │
└────────────────┬────────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────────┐
│  6. Run calibration in thread                       │
│     - Emit progress updates                         │
│     - Handle success/failure                        │
└────────────────┬────────────────────────────────────┘
                 │
    ┌────────────┴────────────┐
    │ SUCCESS                 │ FAILURE
    v                         v
┌────────────────────┐   ┌──────────────────────┐
│ 7a. Success path:  │   │ 7b. Failure path:    │
│ - Set _completed=T │   │ - Set _running=F     │
│ - Show results     │   │ - Show error dialog  │
│ - Clear graphs     │   │ - NO graph clear     │
│ - Resume live data │   │ - NO live resume     │
│ - Set _running=F   │   └──────────────────────┘
└────────────────────┘
```
