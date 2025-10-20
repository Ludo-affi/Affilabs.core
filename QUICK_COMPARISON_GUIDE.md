# Quick Performance Check - What to Look For

**Date**: October 19, 2025  
**Purpose**: Quick guide for comparing new vs old software

---

## 🎯 Top 3 Things to Check

### 1. **Speed** ⏱️
- **Look at**: Sensorgram update frequency
- **Count**: How many data points appear in 1 minute?
- **Expected**: ~50 updates/minute (0.83 Hz, 1.2s per cycle)
- **Old software**: Probably ~25-30 updates/minute

### 2. **Smoothness** 📊
- **Look at**: Baseline (flat region, no sample)
- **Check**: Is the line smooth or jumpy?
- **Expected**: Gentle variations, <2 RU peak-to-peak
- **Red flag**: Wild spikes, >5 RU variations

### 3. **Responsiveness** 🖱️
- **Feel**: Does the GUI respond quickly?
- **Check**: Click different tabs, does it freeze?
- **Expected**: Smooth, no lag
- **Red flag**: Choppy updates, delays

---

## 📊 Visual Quality Check

### Good Baseline (Target)
```
670 RU ├─────────────────────────────────────
       │ ~~~~~~~~~~~~~~~~~~~~~~~~~~ (gentle noise)
668 RU ├─────────────────────────────────────
       │
666 RU └─────────────────────────────────────
         0s        30s        60s        90s
```
✅ Smooth, <2 RU variations

### Poor Baseline (Problem)
```
672 RU ├─────────────────────────────────────
       │  ╱╲    ╱╲      ╱╲   ╱╲  (wild spikes)
668 RU ├────╲╱──────────────────╲╱───────────
       │        ╲╱    ╲╱
664 RU └─────────────────────────────────────
         0s        30s        60s        90s
```
❌ Spiky, >5 RU variations

---

## ⚡ Performance Indicators

### Console Output to Watch

**Good Signs** ✅:
```
Centroid method: λ=665.234nm
Cycle time: 1.203s
Peak tracking successful
```

**Warning Signs** ⚠️:
```
Centroid: Fallback to simple minimum
Peak tracking failed, using fallback
```

**Bad Signs** ❌:
```
Error in peak detection
NaN value detected
Exception in find_peak_centroid
```

---

## 🔧 Quick Fixes

### If Too Noisy (>3 RU)
1. **Try enhanced method**: Change `PEAK_TRACKING_METHOD = 'enhanced'`
2. **Increase integration**: Change `INTEGRATION_TIME_MS = 50.0`
3. **Both**: Do both above (back to Phase 3B: 1.43s/cycle)

### If Too Slow (feels laggy)
1. **Check method**: Should be 'centroid' (not 'enhanced')
2. **Check integration**: Should be 40.0 (not higher)
3. **Check diagnostics**: Should be disabled in console

### If Errors/NaN Values
1. **Switch to enhanced**: `PEAK_TRACKING_METHOD = 'enhanced'`
2. **Check calibration**: May need fresh calibration
3. **Check range**: Verify SPR peak is in 600-720nm range

---

## 📝 Quick Comparison Template

Fill this in while watching both systems:

```
Old Software:
- Updates per minute: _____
- Baseline smoothness: ☐ Smooth ☐ Noisy
- GUI responsiveness: ☐ Good ☐ Laggy
- Overall impression: ☐ Good ☐ Fair ☐ Poor

New Software (Current Settings):
- Updates per minute: _____
- Baseline smoothness: ☐ Smooth ☐ Noisy  
- GUI responsiveness: ☐ Good ☐ Laggy
- Overall impression: ☐ Good ☐ Fair ☐ Poor

Winner: ☐ Old ☐ New ☐ About the same

Notes:
_________________________________
_________________________________
```

---

## 🎯 Decision Helper

### New is BETTER → ✅ Keep all settings
- Faster + Similar quality = Perfect!
- Document and move on

### New is SAME → ✅ Keep it anyway
- Modernized code, easier maintenance
- Room for future improvements

### New is SLIGHTLY WORSE → ⚖️ Adjust
- Try enhanced method first (adds 13ms)
- Try 50ms integration if still issues
- Trade-off: Speed vs Quality

### New is MUCH WORSE → ❌ Investigate
- Something may be wrong
- Check calibration, hardware
- May need deeper troubleshooting

---

## 💡 Pro Tips

1. **Let it stabilize**: Wait 5 min after startup before judging
2. **Compare apples-to-apples**: Same calibration, same conditions
3. **Multiple runs**: One test isn't enough, try 2-3 times
4. **Write it down**: Don't rely on memory, document observations

---

## 🚀 Current Optimizations Active

You're running with:
- ✅ 40ms integration (was 50ms) = 160ms faster
- ✅ Centroid method (was enhanced) = 52ms faster  
- ✅ No diagnostic overhead = 15ms faster
- ✅ Reduced logging = 2ms faster
- ✅ All Phase 1-3 optimizations = ~257ms faster

**Total**: ~486ms faster (50% improvement from 2.4s → 1.2s)

---

## 📞 What to Report

When you're ready to decide, note:
1. **Speed comparison**: "Old: ~X updates/min, New: ~Y updates/min"
2. **Quality**: "Baseline noise: Old: X RU, New: Y RU"
3. **Feel**: "Responsiveness: Old was [good/ok/poor], New is [better/same/worse]"
4. **Decision**: "Recommend: [ADOPT/ADJUST/REVERT] because..."

That's all we need to make a good decision! 🎯
