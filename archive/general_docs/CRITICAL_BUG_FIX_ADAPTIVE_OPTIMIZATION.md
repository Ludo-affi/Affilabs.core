# CRITICAL BUG: Adaptive Optimization Not Triggering

## Root Cause Analysis

### What Happened
Channels A and D achieved only **31K counts** in P-mode (well below the 53K target), but the adaptive optimization loop **never triggered**.

### Why It Failed

1. **Wrong Criteria**: The code checks `p_weakest_led < 220` (LED intensity)
2. **Wrong Data**: Should check actual **signal counts** from P-ref, not LED intensity
3. **Wrong Timing**: The check happens BEFORE P-ref is captured, so no signal data exists yet
4. **Empty Dict**: `p_mode_intensities` appears to be empty `{}` in your run, causing the check to fail silently

### The Bug
```python
# Line ~1035 - WRONG!
while p_weakest_led < P_MODE_LED_TARGET_MIN and p_iteration < MAX_P_MODE_ITERATIONS:
```

This checks:
- **LED intensity** < 220 (wrong metric!)
- **Before** P-ref capture (no signal data available!)

### What Should Happen
1. Capture P-ref signals first
2. Analyze actual **signal counts** (not LED intensity)
3. If weakest channel < 45K counts → trigger optimization
4. Increase integration time and re-optimize

## The Fix

### Change 1: Use Signal Counts, Not LED Intensity
```python
# OLD (WRONG):
P_MODE_LED_TARGET_MIN = 220  # LED intensity threshold
while p_weakest_led < P_MODE_LED_TARGET_MIN:

# NEW (CORRECT):
P_MODE_SIGNAL_TARGET_MIN = 45000  # Signal count threshold
while p_weakest_signal_counts < P_MODE_SIGNAL_TARGET_MIN:
```

### Change 2: Move Check AFTER P-ref Capture
```python
# 1. Capture P-ref first
p_ref_signals = measure_reference_signals(...)

# 2. THEN analyze signal counts
p_signal_max = {}
for ch in ch_list:
    p_signal_max[ch] = np.max(p_ref_signals[ch])

p_weakest_signal_ch = min(p_signal_max, key=p_signal_max.get)
p_weakest_signal_counts = p_signal_max[p_weakest_signal_ch]

# 3. NOW check if optimization needed
if p_weakest_signal_counts < P_MODE_SIGNAL_TARGET_MIN:
    # Trigger adaptive optimization
```

### Change 3: Target 45K Counts (Not 220 LED)
Your channels are:
- Ch A: 31K counts ← **NEEDS OPTIMIZATION**
- Ch D: 30K counts ← **NEEDS OPTIMIZATION**
- Target: 45K counts (approximately 70% of 65K max)

## Implementation

The fix requires:
1. Remove the adaptive loop from lines 1018-1327 (wrong location)
2. Capture P-ref first (line ~1340)
3. Add signal analysis AFTER P-ref capture
4. Check `p_weakest_signal_counts < 45000`
5. If true, trigger adaptive optimization loop

## Expected Behavior After Fix

```
Step 6A: P-mode LED optimization complete
Capturing P-mode references...
✅ P-mode references captured

📊 P-MODE SIGNAL ANALYSIS
P-mode signal counts:
   Ch A: 31046 counts (LED=255)
   Ch B: 49296 counts (LED=180)
   Ch C: 49341 counts (LED=185)
   Ch D: 30219 counts (LED=255)

Weakest channel: A at 31046 counts
Target minimum: 45000 counts

⚠️ WEAK P-MODE SIGNAL DETECTED
   Deficit: 13954 counts
🔄 ADAPTIVE OPTIMIZATION NEEDED

=================================================
🔄 P-MODE ADAPTIVE OPTIMIZATION - ITERATION #1
=================================================
Strategy: Increase integration time to boost signal
   Current: 36ms → Proposed: 43ms (+20%)
   Re-optimizing P-mode LEDs...
   Recapturing P-mode references...

📊 Iteration #1 Results:
   Ch A: 37000 counts
   Ch D: 36000 counts
   Still below target - continuing...

[Iteration #2...]
   Ch A: 44000 counts
   Ch D: 43000 counts
   Still below target - continuing...

[Iteration #3...]
   Ch A: 47000 counts ✅
   Ch D: 45500 counts ✅
   ✅ SUCCESS: Target reached!
```

## Action Required

Run the fix script to:
1. Replace LED intensity check with signal count check
2. Move optimization loop AFTER P-ref capture
3. Change target from 220 LED → 45000 counts
4. Re-test calibration

The optimization should now trigger automatically for your device's weak channels A & D.
