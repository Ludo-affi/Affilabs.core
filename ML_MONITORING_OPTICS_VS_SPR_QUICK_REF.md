# ML Monitoring System: Optics vs SPR vs Experimental Attribution

**Quick Reference Guide**

---

## The Problem

During live SPR measurements, signal changes can come from:
1. **Device (Optics)**: LED, detector, fiber, optical system
2. **Consumable (Sensor Physical)**: Water coupling, sensor chip degradation
3. **Experimental/Biology**: Buffer, chemistry, temperature, binding (EXPECTED!)
4. **Calibration**: S_ref aging

**System must distinguish these FOUR categories to provide correct user actions!**

---

## Decision Logic

### Step 1: Multi-Channel Check

**If all 4 channels show the same change:**
→ Could be **DEVICE** or **EXPERIMENTAL** (shared conditions)
- Check: Background slope → DEVICE (LED spectrum)
- Check: Temperature correlation → EXPERIMENTAL
- Check: Flow correlation → EXPERIMENTAL

**If only 1-2 channels affected:**
→ Could be **SENSOR** or **SAMPLE-SPECIFIC**
- Check: Reversible binding pattern → EXPERIMENTAL (biology)
- Check: FWHM broadening → SENSOR (degradation)
- Check: Water loss → SENSOR (physical)

### Step 2: Feature Pattern

| Feature | Device/Optics | Sensor Physical | Experimental/Biology |
|---------|--------------|----------------|---------------------|
| Background slope changes | ✅ | ❌ | ❌ |
| Entire spectrum scales | ✅ | ❌ | ❌ |
| Only SPR dip affected | ❌ | ✅ | ✅ |
| Reversible pattern | ❌ | ❌ | ✅ (binding) |
| Temperature correlated | ⚠️ (electronics) | ⚠️ (gold thermal) | ✅ (bulk RI) |
| Flow correlated | ❌ | ⚠️ (drying) | ✅ (mass transport) |

### Step 3: Temporal Behavior

| Pattern | Likely Source |
|---------|---------------|
| Gradual drift (hours), irreversible | Device (LED aging) |
| Step change, irreversible | Sensor (water loss) |
| Smooth curve, reversible | Experimental (binding - SIGNAL!) |
| Oscillating | Experimental (temp cycling, flow) |

---

## User Actions

| Classification | User Action | Category | Icon |
|----------------|-------------|----------|------|
| `DEVICE_OPTICS: LED_DRIFT` | Recalibrate system | Hardware | 🔧 |
| `DEVICE_OPTICS: DETECTOR_NOISE` | Check USB connection | Hardware | ⚠️ |
| `SENSOR_PHYSICAL: WATER_LOSS` | **STOP** - Add water | Consumable | 🚨 |
| `SENSOR_PHYSICAL: SENSOR_DEGRADED` | Replace sensor | Consumable | 🔴 |
| `EXPERIMENTAL_BIOLOGY: BINDING_EVENT` | **Normal - continue** | Expected Signal | ✅ |
| `EXPERIMENTAL: TEMPERATURE_EFFECT` | Expected physics | Expected Signal | 🌡️ |
| `EXPERIMENTAL: FLOW_EFFECT` | Mass transport | Expected Signal | 💧 |
| `EXPERIMENTAL: BUFFER_MISMATCH` | Check buffer matching | Experimental | ⚗️ |
| `EXPERIMENTAL_BIOLOGY: NON_SPECIFIC_BINDING` | Check sample purity | Experimental | ⚠️ |
| `CALIBRATION_STALE` | Recalibrate (>2h old) | Calibration | 🔄 |

---

## Implementation Files

| File | Purpose |
|------|---------|
| `docs/analysis/LIVE_MONITORING_OPTICS_VS_SPR_SEPARATION.md` | **Complete strategy (read this!)** |
| `docs/analysis/SPECTRAL_ML_ANALYSIS_FRAMEWORK.md` | Physics models, algorithm bias |
| `Affilabs.core beta/CALIBRATION_MASTER.md` | S-mode (optics) vs P-mode (SPR) QC |
| `utils/led_health_monitor.py` | LED degradation tracking (optics) |
| `core/fmea_integration.py` | Failure mode logging |
| `tools/spectral_quality_analyzer.py` | Feature extraction |

---

## Key Equations

**Transmission (live measurement):**
```
T_live(λ, t) = P_live(λ, t) / S_ref(λ)
```

**Full Reality:**
```
T_live = [LED × Optics × SPR_sensor × (Buffer + Temp + Chemistry + Biology)] / S_ref
```

**Assumptions:**
- S_ref captured at calibration (LED + Optics baseline)
- P_live includes everything: device + sensor + experimental
- **Challenge**: Deconvolve 4 sources from single measurement!

**Solution:** Multi-channel correlation + feature patterns + temporal analysis + physics models

---

## The 4 Categories

| Category | Examples | Multi-Channel | Reversible | Action Domain |
|----------|----------|---------------|------------|---------------|
| **DEVICE** | LED drift, detector noise | HIGH (>0.8) | NO | Hardware/calibration |
| **SENSOR** | Water loss, degradation | LOW (<0.3) | NO | Replace consumable |
| **EXPERIMENTAL** | Binding, temperature, flow | VARIES | YES | Expected behavior |
| **CALIBRATION** | S_ref >2h old | HIGH | N/A | Recalibrate |

---

## Testing Checklist

**Device Issues (should flag as hardware):**
- [ ] Reduce LED intensity → "LED_INTENSITY_DRIFT"
- [ ] Wait 4 hours after calibration → "CALIBRATION_STALE"
- [ ] Disconnect fiber briefly → "DETECTOR_NOISE"
- [ ] **All 4 channels affected equally** ✅

**Sensor Physical Issues (should flag as consumable):**
- [ ] Let water evaporate → "WATER_LOSS"
- [ ] Use recycled sensor → "SENSOR_DEGRADED"
- [ ] **Single channel affected, irreversible** ✅

**Experimental/Biology Issues (should flag as expected or info):**
- [ ] Inject analyte → "BINDING_EVENT" (not error!)
- [ ] Change temperature → "TEMPERATURE_EFFECT"
- [ ] Change flow rate → "FLOW_EFFECT"
- [ ] **Reversible or correlated with protocol** ✅

---

## Remember

✅ **Multi-channel correlation is PRIMARY for device vs sensor/experiment**
✅ **Reversibility distinguishes sensor physical (permanent) from experimental (reversible)**
✅ **Temperature/flow correlation identifies experimental factors**
✅ **Binding curves are EXPECTED SIGNAL - not errors!**
✅ **Buffer, chemistry, biology sit "above" the sensor - part of experimental layer**

❌ **Don't confuse binding (experimental/biology) with sensor drift (physical)**
❌ **Don't flag temperature effects as hardware issues**
❌ **Don't ignore flow-correlated changes - could be mass transport (expected)**
❌ **Don't assume channel-specific = always sensor (could be different samples!)**

---

**Critical Insight:** The sensor surface sees EVERYTHING above it: buffer composition, pH, temperature, flow shear, analyte concentration, aggregates, contaminants. ML must separate "device broke" from "sensor broke" from "experiment is doing what it should"!

---

**Last Updated:** November 23, 2025
**Status:** IMPLEMENTED in documentation, PENDING code implementation
