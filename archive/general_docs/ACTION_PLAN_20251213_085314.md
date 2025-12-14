# SPR Instrument Optimization - Lean Action Plan

## 🎯 Philosophy: Minimal Viable Proof

**Fastest path to prove the optimization approach works** - minimum experiments, maximum insight.

Don't optimize everything. Prove the concept end-to-end with **ONE channel**, **ONE sensor**, **minimal data**.

---

## 📊 Current Status (Baseline)

### Your Test Data Analysis (test.csv)

| Channel | P2P (RU) | Noise (RU) | Wavelength Std (nm) | Grade | Status |
|---------|----------|------------|---------------------|-------|---------|
| **A** | **11.5** | **2.16** | **0.09** ✅ | **B** | **EXCELLENT - Reference** |
| B | 67.2 | 14.12 | 1.01 ⚠️ | D | LED unstable |
| C | 47.4 | 10.66 | 0.42 | B | Good instrument |
| D | 88.7 | 16.76 | 0.77 | C | Moderate issues |

### Key Findings:
✅ **Channel A is reference-quality** - proves fixes are working
⚠️ **Channel B has LED instability** - wavelength drift (1.01 nm) suggests LED issue
⚠️ **Channels C & D have higher noise** - but good instrumental scores

### What This Means:
1. Your LED delay fix (2.6ms → 20ms) **IS WORKING** (Channel A proves this)
2. Channel B needs specific LED attention (different issue than A/C/D)
3. Consumable quality may be contributing to C/D noise (but instrument is solid)

---

## ⚡ Proof-of-Concept Path (3 Days, Not 4 Weeks!)

**Goal**: Prove we can distinguish instrument vs sensor issues with minimal data

### The Lean Strategy:
1. **ONE channel** (Channel A - already excellent)
2. **TWO measurements** (one excellent sensor, one poor sensor)
3. **ONE analysis** (does the tool correctly identify the difference?)
4. **Decision point**: If YES → scale up. If NO → fix approach first.

### Day 1: Proof of Concept (2 hours)

**Objective**: Prove the analysis system can distinguish sensor quality

**Experiment**: Run TWO measurements on Channel A:
1. **Excellent sensor** (fresh chip, <1 week old, good storage)
2. **Poor sensor** (old chip, >6 months, or visibly degraded)

```python
from training_data_manager import TrainingDataManager
tdm = TrainingDataManager(device_id="device_001")

# Measurement 1: Excellent sensor
tdm.save_p_signal(
    detector="A",
    sensor_quality="excellent",
    chip_batch="FRESH-001",
    csv_path="excellent_sensor.csv",
    metadata={
        "chip_age_days": 5,
        "storage_temp": 4.0,
        "ri_medium": 1.3333,
        "visual_inspection": "perfect"
    }
)

# Measurement 2: Poor sensor
tdm.save_p_signal(
    detector="A",
    sensor_quality="poor",
    chip_batch="OLD-001",
    csv_path="poor_sensor.csv",
    metadata={
        "chip_age_days": 180,
        "storage_temp": 20.0,
        "ri_medium": 1.3333,
        "visual_inspection": "discolored"
    }
)

# Compare
python compare_sensors.py excellent_sensor.csv poor_sensor.csv
```

**Success Criteria** (Go/No-Go Decision):
- ✅ **GO**: Analysis clearly shows difference (consumable score drops for poor sensor)
- ❌ **NO-GO**: Analysis can't distinguish → fix the feature extraction first

**Time**: 2 hours (15min warm-up, 2×30min measurements, 15min analysis)

**Deliverable**: PROOF that the approach works (or doesn't)

---

### Day 2: Instrument vs Sensor Test (1 hour)

**Objective**: Prove we can distinguish instrument issues from sensor issues

**Experiment**: ONE measurement with excellent sensor on Channel B (the "bad" channel)

```python
# Channel B with EXCELLENT sensor
# Question: Does Channel B still show poor performance?
# If YES → Instrument issue (LED)
# If NO → Previous test.csv had sensor issue

tdm.save_p_signal(
    detector="B",
    sensor_quality="excellent",
    chip_batch="FRESH-001",
    csv_path="channel_b_excellent.csv",
    metadata={
        "chip_age_days": 5,
        "storage_temp": 4.0,
        "ri_medium": 1.3333,
        "notes": "Testing if Channel B issue is LED or sensor"
    }
)

# Compare to Channel A with same excellent sensor
python compare_sensors.py excellent_sensor.csv channel_b_excellent.csv
```

**Decision Tree**:
```
Channel B wavelength std still high (>0.5 nm)?
├─ YES → Instrument issue confirmed (LED needs attention)
│         Action: Focus on LED optimization (Day 3)
└─ NO  → Previous issue was sensor quality
          Action: Your test.csv just had a poor sensor on Channel B
```

**Time**: 1 hour (measurement + analysis)

**Deliverable**: Root cause identified (instrument vs sensor)

---

### Day 3: Quick Optimization Test (IF needed, 2 hours)

**Only do this if Day 2 shows Channel B has instrument issue**

**Objective**: Find the fix with minimal testing

**Experiment**: Test ONLY the most likely fixes (not full sweep)

```python
# Test only 2-3 LED delays (not 6!)
# Pick: current (20ms), lower (15ms), higher (30ms)
for delay in [15, 20, 30]:
    tdm.save_s_signal(
        detector="B",
        category="led_testing",
        csv_path=f"led_{delay}ms.csv",
        metadata={"led_delay_ms": delay, "warm_up_min": 15}
    )

# Immediately analyze - does wavelength std improve?
# If YES at 30ms → implement 30ms for Channel B
# If NO improvement → hardware issue, document and move on
```

**Success Criteria**:
- ✅ Find a setting that improves wavelength std by 50%+
- OR
- ✅ Confirm hardware issue (no software fix possible)

**Time**: 2 hours max

**Deliverable**: Quick fix implemented OR hardware issue documented

---

## 🎯 3-Day Proof-of-Concept Summary

**Total Time**: 5 hours of active work (spread over 3 days for warm-up)
**Total Measurements**: 4-6 (not 50+!)
**Total Data Points**: ~10

### What You Prove:

**Day 1** (2 measurements):
- ✅ Analysis distinguishes excellent vs poor sensors
- ✅ Training data system works
- ✅ Approach is valid

**Day 2** (1 measurement):
- ✅ Can identify if issue is instrument or sensor
- ✅ Root cause of Channel B identified

**Day 3** (2-3 measurements, optional):
- ✅ Quick fix found OR hardware issue documented

### Decision Point: Scale or Pivot?

**If all 3 days successful**:
→ Approach validated! Now scale up:
  - Add more channels
  - Add more sensor qualities
  - Build comprehensive dataset
  - Develop prediction models

**If Day 1 fails**:
→ Fix feature extraction before collecting more data
→ Don't waste time on measurements that won't help

**If Day 2 shows all issues are sensors**:
→ Your instrument is already optimized!
→ Focus on sensor quality models only

---

## 📊 Minimal Viable Data

**3-Day POC**: 4-6 measurements
**Proof achieved**: End-to-end concept validated

**If successful, THEN scale**:
- Week 2: Add 2-3 more quality levels (good, acceptable)
- Week 3: Add other channels (if needed based on Day 2)
- Week 4: Collect 10-20 more samples for model training

**Don't collect 100 samples before proving it works!**

---

## � Decision Gates (Go/No-Go)

### After Day 1:
**Question**: Does the analysis distinguish sensor quality?
- ✅ **GO** → Proceed to Day 2
- ❌ **NO-GO** → Stop. Fix analysis features before more measurements

### After Day 2:
**Question**: Is root cause identified (instrument vs sensor)?
- ✅ **YES - Instrument** → Day 3 (quick fix attempt)
- ✅ **YES - Sensor** → Skip Day 3, you're done! Instrument is fine
- ❌ **UNCLEAR** → Review analysis, may need 1 more measurement

### After Day 3:
**Question**: Is the approach validated end-to-end?
- ✅ **YES** → Scale up (more channels, more qualities, more data)
- ❌ **NO** → Pivot approach before collecting more data

---

## 🎯 Immediate Next Action (Today/Tomorrow)

### **Day 1 POC** (2 hours total)

**Step 1**: Get TWO sensors ready
- ✅ One fresh, excellent quality chip (<1 week old)
- ✅ One poor quality chip (>6 months OR visibly degraded)

**Step 2**: Run measurements (15min warm-up, then 30min each)
```python
from training_data_manager import TrainingDataManager
tdm = TrainingDataManager("device_001")

# Measurement 1: Excellent
tdm.save_p_signal("A", "excellent", "FRESH-001", "excellent.csv",
                  metadata={"chip_age_days": 5, "storage_temp": 4.0})

# Measurement 2: Poor
tdm.save_p_signal("A", "poor", "OLD-001", "poor.csv",
                  metadata={"chip_age_days": 180, "storage_temp": 20.0})
```

**Step 3**: Analyze (5 minutes)
```bash
python compare_sensors.py excellent.csv poor.csv
```

**Step 4**: Decision
- **Can you see clear difference?** → GO to Day 2
- **No clear difference?** → Fix analysis first, don't collect more data yet

---

## � Key Philosophy Principles Applied

### 1. **Minimal Viable Experiment**
- 2 measurements prove the concept (not 50)
- One channel (not 4)
- One decision point per day

### 2. **Fast Feedback Loops**
- Each day has clear go/no-go decision
- Don't continue if Day 1 fails
- Don't optimize everything if only one channel needs it

### 3. **Prove Before Scale**
- Day 1: Prove analysis works
- Day 2: Prove we can diagnose
- Day 3: Prove we can fix
- THEN scale up

### 4. **Don't Optimize Prematurely**
- Channel A is already excellent (11.5 RU)
- Don't "optimize" what's already working
- Focus only on what's broken (Channel B?)

### 5. **Data Efficiency**
- Each measurement must answer a specific question
- No "let's collect more data just in case"
- Stop collecting when decision is made

---

## 📊 Expected Outcomes (3 Days)

### After Day 1 (2 measurements):
✅ Proof that analysis distinguishes sensor quality
✅ Know if the approach is valid
✅ Go/No-Go decision made

### After Day 2 (3 measurements total):
✅ Root cause identified (instrument vs sensor)
✅ Know where to focus efforts
✅ No wasted optimization on wrong problem

### After Day 3 (5-6 measurements total):
✅ Quick fix implemented (if possible)
✅ OR hardware issue documented
✅ End-to-end concept validated
✅ Ready to scale (or pivot if needed)

**Total Investment**: 5 hours, 6 measurements, 3 days

**Return**: Complete understanding of what works and what doesn't

---

## 🎉 Lean Summary

**Timeline**: 3 days (not 4 weeks)
**Measurements**: 4-6 (not 100+)
**Focus**: Prove concept → THEN scale
**Philosophy**: Fast feedback, minimal viable experiments, no premature optimization

**Start tomorrow**: Get 2 sensors (excellent + poor), run Day 1 POC

Your training data system is ready. Now prove it works with minimal data! 🚀
