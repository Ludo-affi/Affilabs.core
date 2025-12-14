# Training Data System - Quick Start

## ✅ System Deployed

Your training data management system is now operational!

## 📁 What Was Created

1. **`training_data_manager.py`** - Core data management system
2. **`TRAINING_DATA_GUIDE.md`** - Complete documentation
3. **`examples_training_integration.py`** - Integration examples
4. **`training_data/`** directory - Hierarchical storage

## 🎯 Architecture Implemented

### Data Organization

```
training_data/
└── device_001/                    # Your instrument
    ├── device_info.json           # Hardware specs (LED, detector serials)
    ├── detector_A/
    │   ├── s_signal/              # Pure instrument (no sensor dependency)
    │   │   ├── baseline/          # Standard reference
    │   │   ├── thermal/           # Warm-up studies
    │   │   ├── stability/         # Long-term drift
    │   │   ├── led_testing/       # LED optimization
    │   │   └── noise_floor/       # Dark measurements
    │   └── p_signal/              # With sensor (transmission spectra)
    │       ├── sensor_excellent/  # Reference quality
    │       ├── sensor_good/
    │       ├── sensor_acceptable/
    │       ├── sensor_poor/
    │       └── sensor_defective/
    ├── detector_B/
    ├── detector_C/
    └── detector_D/
```

### ✅ Already Saved

Your `test.csv` is now saved as:
```
training_data/device_001/detector_A/s_signal/baseline/s_signal_20251022_102537/
├── measurement.csv    # Your data
└── metadata.json      # Warm-up: 15min, Temp: 23.5°C
```

## 🚀 Quick Usage

### Python API

```python
from training_data_manager import TrainingDataManager

# Initialize
tdm = TrainingDataManager(device_id="device_001")

# Save S-signal (instrument characterization)
tdm.save_s_signal(
    detector="A",
    category="baseline",
    csv_path="measurement.csv",
    metadata={"warm_up_min": 15, "ambient_temp": 23.5}
)

# Save P-signal (with sensor)
tdm.save_p_signal(
    detector="A",
    sensor_quality="excellent",
    chip_batch="ABC-2025-10",
    csv_path="measurement.csv",
    metadata={
        "chip_age_days": 5,
        "storage_temp": 4.0,
        "ri_medium": 1.3333
    }
)

# Query data
baselines = tdm.get_s_signal_data(detector="A", category="baseline")
excellent_chips = tdm.get_p_signal_data(detector="A", quality="excellent")

# Statistics
stats = tdm.get_device_statistics()
print(f"Total measurements: {stats['total_measurements']}")
```

### Command Line

```bash
# Initialize device
python training_data_manager.py --device device_001 init

# Save S-signal
python training_data_manager.py --device device_001 save-s \
    --detector A --category baseline \
    --csv test.csv --warmup 15 --temp 23.5

# Save P-signal
python training_data_manager.py --device device_001 save-p \
    --detector A --quality excellent --batch "ABC-2025-10" \
    --csv chip_test.csv --chip-age 5 --ri 1.3333

# View statistics
python training_data_manager.py --device device_001 stats

# Export for training
python training_data_manager.py --device device_001 export \
    --output training_dataset.json
```

## 📊 Phase 1 Workflow: Instrument Characterization

### This Week: Repeatability Study

```python
from training_data_manager import TrainingDataManager
tdm = TrainingDataManager(device_id="device_001")

# Run same chip 3 times (30 min apart)
for i in range(3):
    tdm.save_s_signal(
        detector="A",
        category="baseline",
        csv_path=f"repeatability_run{i+1}.csv",
        metadata={
            "warm_up_min": 15,
            "run_number": i+1,
            "notes": "Same chip, instrument repeatability test"
        }
    )
```

**Goal**: Confirm instrument variation is <5% (proves stability)

### Next Week: Channel B LED Fix

```python
# Test LED delay variations for Channel B
for delay in [15, 20, 25, 30]:
    tdm.save_s_signal(
        detector="B",
        category="led_testing",
        csv_path=f"channel_b_led_{delay}ms.csv",
        metadata={
            "led_delay_ms": delay,
            "warm_up_min": 15,
            "notes": f"Wavelength stability test at {delay}ms delay"
        }
    )
```

**Goal**: Fix Channel B wavelength instability (currently 1.01 nm)

### Week 3-4: P-Signal Baseline (Excellent Sensors)

```python
# Use fresh reference chips
for i in range(5):
    tdm.save_p_signal(
        detector="A",
        sensor_quality="excellent",
        chip_batch="REFERENCE-2025-10",
        csv_path=f"reference_chip_{i+1}.csv",
        metadata={
            "chip_age_days": 3,
            "storage_temp": 4.0,
            "ri_medium": 1.3333,
            "chip_number": i+1
        }
    )
```

**Goal**: Establish peak tracking baseline with excellent sensors

## 🔑 Key Concepts

### S-Signal (Reference Polarization)
- **Pure instrument characterization**
- Minimal sensor dependency
- Quantifies: LED stability, detector noise, thermal behavior
- Medium: Water (1.3333 RIU)

### P-Signal (Measurement Polarization)
- **Sensor-specific characterization**
- Shows resonance dip (transmission spectrum)
- Quantifies: Chip quality, coating uniformity, peak tracking
- Medium: Water (1.3333 RIU)

### Sensor Quality Levels
- **excellent**: Fresh (<1 week), perfect storage, reference quality
- **good**: Normal (1-3 months), proper storage
- **acceptable**: Older (3-6 months), some degradation
- **poor**: Degraded (>6 months), storage issues
- **defective**: Known defects, contamination, failure analysis

## 📈 What Gets Saved

Each measurement saves:
1. **CSV file**: Raw sensorgram data
2. **metadata.json**: Collection conditions (warm-up, temp, chip info, etc.)
3. **analysis.json**: Automatic spectral quality analysis (if analyzer available)

Example metadata:
```json
{
  "measurement_id": "s_signal_20251022_102537",
  "timestamp": "2025-10-22T10:25:37",
  "device_id": "device_001",
  "detector": "A",
  "signal_type": "S",
  "category": "baseline",
  "warm_up_min": 15.0,
  "ambient_temp": 23.5
}
```

## 🎯 Current Status

### Your Data
- ✅ Device initialized: `device_001`
- ✅ First measurement saved: Channel A baseline S-signal
- ✅ Metadata captured: 15min warm-up, 23.5°C

### Next Actions
1. **Update device info** with hardware details:
   ```python
   tdm.update_device_info(
       **{
           "hardware.led_model": "PICOP4SPR",
           "hardware.led_serial": "YOUR_SERIAL",
           "hardware.detector_model": "Hamamatsu C12880MA"
       }
   )
   ```

2. **Collect repeatability data**: Run 3 measurements with same chip

3. **Characterize all channels**: Save baseline for A, B, C, D

4. **Optimize Channel B**: LED delay testing to fix wavelength instability

## 🔮 Future: Model Training

Once you have 50+ measurements per detector:

```python
# Export consolidated dataset
tdm.export_training_dataset(
    output_file="detector_a_training.json",
    detector="A"
)

# Use for:
# - Peak tracking optimization
# - Noise prediction models
# - Sensor quality classification
# - Instrument health monitoring
```

## 📞 Integration with Existing Code

Add to your SPR acquisition script:

```python
from training_data_manager import TrainingDataManager

# Initialize once
tdm = TrainingDataManager(device_id="device_001")

# After every measurement, save to training database
def save_to_training(csv_path, detector, signal_type, **metadata):
    if signal_type == "S":
        tdm.save_s_signal(
            detector=detector,
            category="baseline",  # or other category
            csv_path=csv_path,
            metadata=metadata
        )
    elif signal_type == "P":
        tdm.save_p_signal(
            detector=detector,
            sensor_quality=metadata.get("quality", "good"),
            chip_batch=metadata.get("batch", "UNKNOWN"),
            csv_path=csv_path,
            metadata=metadata
        )
```

## ✅ Benefits

1. **Organized**: Hierarchical by device → detector → signal → quality
2. **Automatic**: Analysis runs on every save
3. **Queryable**: Find specific measurement types easily
4. **Exportable**: Consolidate for ML training
5. **Multi-device**: Track multiple instruments
6. **Reproducible**: Full context for every measurement

## 📚 Documentation

- **`TRAINING_DATA_GUIDE.md`** - Complete guide with examples
- **`SPECTRAL_ANALYSIS_SYSTEM_README.md`** - Analysis system overview
- **`SPECTRAL_QUALITY_TRAINING_GUIDE.md`** - Feature explanations

---

**Your training data system is ready to use!** 🎉

Start collecting data now to build your instrument characterization model.
