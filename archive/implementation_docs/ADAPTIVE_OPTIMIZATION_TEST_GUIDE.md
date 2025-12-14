# Quick Test Guide - Adaptive P-Mode Optimization

## 🚀 Ready to Test!

The full adaptive P-mode optimization system is implemented and ready for testing.

---

## What to Expect

### Scenario 1: Normal Device (No Weak Channels)
```
Result: No adaptive optimization triggers
Time: Normal calibration time (~60 seconds)
Log: "Weakest LED: 230" (or higher)
```

### Scenario 2: Your Device (Weak Channels A & D)
```
Initial P-mode: A=180, D=185
Target: 220 minimum

Expected:
✅ Iteration 1: Integration 80ms → 96ms
✅ Re-optimize P-mode LEDs
✅ Result: A=215-225, D=220-230
✅ SUCCESS: Target reached!

Time: ~30-45 seconds additional
```

### Scenario 3: Very Weak Channels (Unlikely)
```
Initial P-mode: A=160, D=165

Expected:
⚠️ Full S+P recalibration triggered
⚠️ Multiple iterations (2-3)
⚠️ Integration time increases to 100ms
✅ Either reaches target or LED=255

Time: ~90-120 seconds additional
```

---

## What to Watch For

### Success Indicators ✅
- Weakest LED reaches 220+ within 1-2 iterations
- Integration time stays below 10% change (no S-mode recal)
- Logs show "SUCCESS: Weakest LED reached target!"
- Total calibration time < 2 minutes

### Normal Warnings ⚠️
- "Integration change below 10% threshold" → Expected, no action needed
- "Still below target" after iteration 1 → Expected, will continue
- "Weakest LED at maximum (255)" → Expected if hardware limited

### Critical Issues ❌
- "S+P Recalibration failed" → Major issue, system reverts to original
- Calibration takes > 3 minutes → May need to investigate
- Repeated failures across iterations → Hardware problem possible

---

## How to Monitor

### Log Messages to Look For

**Adaptive optimization triggered:**
```
🔄 P-MODE ADAPTIVE OPTIMIZATION - ITERATION #1
🎯 Target: Optimize weakest LED (device-specific bottleneck)
   Weakest channel detected: A at LED=180
```

**Small adjustment (< 10%):**
```
✅ Integration change below 10% threshold
S-mode calibration still valid - only updating P-mode
```

**Large adjustment (> 10%):**
```
⚠️ Integration time changed by 12.0% from original
🔄 TRIGGERING FULL S+P RECALIBRATION
```

**Success:**
```
✅ SUCCESS: Weakest LED reached target!
Exiting adaptive optimization loop
```

---

## Quick Diagnostics

### If optimization takes multiple iterations:
- Check which channel is weakest (should be consistent with hardware)
- Verify LED values increasing each iteration
- Monitor integration time (should increase by ~20% each time)

### If optimization fails:
- Check error messages for specific failure
- Verify hardware connections
- Review S-mode initial calibration results
- Check if LED reaching 255 (hardware limit)

### If optimization is too slow:
- Verify pre/post LED delays are correct (45ms/5ms)
- Check USB communication speed
- Ensure no other processes interfering

---

## Expected Log Output (Your Device)

```
[Initial P-mode calibration]
📊 P-MODE LED OPTIMIZATION RESULTS
   Channel A: LED=180, Counts=28000
   Channel D: LED=185, Counts=29000
   Weakest: A at 180 (Target: 220)

🔄 P-MODE ADAPTIVE OPTIMIZATION - ITERATION #1
🎯 Weakest channel: A at LED=180
   Target minimum: 220
   Deficit: 40 LED points

Strategy: Increase P-mode integration time to boost weak channel
   Current: 80ms
   Proposed: 96ms (+16ms)
   ✅ Integration change below 10% threshold
   S-mode calibration still valid - only updating P-mode

   Re-optimizing P-mode LEDs at new integration time...

📊 Iteration #1 Results:
   Weakest LED: Ch A at 220
   Integration time: 96ms
   ✅ SUCCESS: Weakest LED reached target!

📊 P-MODE ADAPTIVE OPTIMIZATION SUMMARY
🎯 Optimized for device-specific weakest channel: A
   Iterations performed: 1
   Integration time: 80ms → 96ms
   Weakest LED final: 220/255
   ✅ SUCCESS: Weakest LED reached target (220)!
```

---

## Testing Steps

1. **Start calibration normally**
   - Run standard 6-step calibration
   - Let it proceed through S-mode optimization
   - Watch for P-mode optimization section

2. **Monitor adaptive optimization**
   - Check if it triggers (weakest LED < 220)
   - Watch iteration progress
   - Verify integration time changes
   - Confirm LED values improving

3. **Verify completion**
   - Check final LED intensities
   - Verify weakest LED ≥ 220 or = 255
   - Confirm calibration completes successfully
   - Review optimization summary

4. **Check results in QC dialog**
   - P-mode reference signals should show good counts
   - All channels should pass validation
   - No saturation warnings

---

## Troubleshooting

### "Already at maximum integration time (80ms)"
- Should not happen (max is 100ms)
- Check if integration_time variable is correct
- May indicate logic error

### "S+P Recalibration failed"
- Check error message for specific cause
- System will revert to original settings
- May need to run calibration again

### Optimization loops 3 times without success
- Normal if hardware limited
- Check if weakest LED = 255 (hardware max)
- Verify optical path is clear
- May need to accept suboptimal result

### Different weak channel than expected
- Hardware consistency check will catch this
- May indicate hardware change
- Review previous calibrations for comparison

---

## Success Criteria

✅ **Optimization worked if:**
- Weakest LED reached 220+ OR
- Weakest LED = 255 (hardware max) OR
- Integration time = 100ms (safety max) OR
- 3 iterations completed (max attempts)

✅ **Calibration quality is good if:**
- P-mode counts > 50,000 for all channels
- No saturation detected
- S-ref and P-ref QC passed
- Optimization completed in < 2 minutes

---

## Next Steps After Testing

1. **If successful:**
   - Document actual behavior vs. expected
   - Note any differences in timing
   - Verify QC metrics are good
   - Proceed with normal operations

2. **If issues found:**
   - Capture full log output
   - Note specific error messages
   - Document hardware state
   - Report for further investigation

3. **If hardware limited:**
   - Document which channels hit LED=255
   - Check if optical transmission is issue
   - Consider servo position validation
   - May be normal for this device

---

## 🎯 You're Ready to Test!

Just run the normal calibration - the adaptive optimization will trigger automatically if needed!

Good luck! 🚀
