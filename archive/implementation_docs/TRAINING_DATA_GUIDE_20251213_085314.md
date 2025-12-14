# Training Data Management System

## 🎯 Architecture Overview

### Hierarchical Data Organization

```
training_data/
├── device_001/                          # Each physical instrument
│   ├── device_info.json                 # Hardware specs, serial numbers
│   ├── detector_A/                      # Per-channel organization
│   │   ├── s_signal/                    # Pure instrument (no sensor impact)
│   │   │   ├── baseline/                # Standard reference measurements
│   │   │   ├── thermal/                 # Warm-up characterization
│   │   │   ├── stability/               # Long-term drift studies
│   │   │   ├── led_testing/             # LED delay optimization
│   │   │   └── noise_floor/             # Dark measurements
│   │   └── p_signal/                    # With sensor (transmission spectra)
│   │       ├── sensor_excellent/        # Reference quality (RI = 1.3333)
│   │       │   ├── chip_batch_A/
│   │       │   │   ├── p_signal_20251022_143022/
│   │       │   │   │   ├── measurement.csv
│   │       │   │   │   ├── metadata.json
│   │       │   │   │   └── analysis.json
│   │       ├── sensor_good/
│   │       ├── sensor_acceptable/
│   │       ├── sensor_poor/
│   │       └── sensor_defective/
│   ├── detector_B/
│   ├── detector_C/
│   └── detector_D/
├── device_002/                          # Another instrument
└── device_003/
```

## 🔬 Signal Types

### S-Signal (Reference Polarization)
- **Purpose**: Pure instrument characterization
- **No sensor dependency**: Minimal interaction with chip coating
- **Uses**: LED stability, detector noise, thermal behavior, optical path quality
- **Medium**: Air or water (1.3333 RIU)

### P-Signal (Measurement Polarization)
- **Purpose**: Sensor-specific characterization
- **Transmission spectra**: Shows resonance dip from gold coating
- **Uses**: Chip quality, coating uniformity, peak tracking optimization
- **Medium**: Water (1.3333 RIU standard)

## 📊 Sensor Quality Levels

| Level | Description | Use Case |
|-------|-------------|----------|
| **excellent** | Reference quality, fresh (<1 week), perfect storage | Baseline performance, algorithm development |
| **good** | Normal quality, proper storage (1-3 months) | Standard production validation |
| **acceptable** | Older but functional (3-6 months), some degradation | Robustness testing |
| **poor** | Degraded (>6 months), storage issues, high noise | Failure mode analysis |
| **defective** | Known defects, contamination, visual damage | Quality control training data |

## 🚀 Usage Examples

### Initialize Training Data for Your Device

```python
from training_data_manager import TrainingDataManager

# Initialize for your specific instrument
tdm = TrainingDataManager(device_id="device_001")

# Update device hardware info
tdm.update_device_info(
    **{
        "hardware.led_model": "PICOP4SPR",
        "hardware.led_serial": "12345",
        "hardware.detector_model": "Hamamatsu C12880MA",
        "hardware.detector_serial": "67890",
        "installation.location": "Lab A - Bench 3",
        "installation.operator": "User Name"
    }
)
```

### Save S-Signal Measurements (Instrument Characterization)

```python
# After running a baseline measurement
tdm.save_s_signal(
    detector="A",
    category="baseline",
    csv_path="C:/Users/lucia/test.csv",
    metadata={
        "warm_up_min": 15,
        "ambient_temp": 23.5,
        "notes": "Post-LED-delay-fix validation"
    }
)

# Thermal stability test
tdm.save_s_signal(
    detector="A",
    category="thermal",
    csv_path="cold_start.csv",
    metadata={
        "warm_up_min": 0,
        "ambient_temp": 22.8,
        "test_type": "immediate_power_on"
    }
)

# LED optimization
tdm.save_s_signal(
    detector="B",
    category="led_testing",
    csv_path="channel_b_led_test.csv",
    metadata={
        "led_delay_ms": 20,
        "led_current_ma": 100,
        "notes": "Testing wavelength stability"
    }
)
```

### Save P-Signal Measurements (With Sensor)

```python
# Excellent reference chip
tdm.save_p_signal(
    detector="A",
    sensor_quality="excellent",
    chip_batch="ABC-2025-10",
    csv_path="fresh_chip.csv",
    metadata={
        "chip_age_days": 3,
        "storage_temp": 4.0,
        "ri_medium": 1.3333,
        "coating_type": "gold_50nm",
        "visual_inspection": "perfect",
        "batch_received": "2025-10-20"
    }
)

# Poor quality chip (for comparison)
tdm.save_p_signal(
    detector="A",
    sensor_quality="poor",
    chip_batch="XYZ-2025-05",
    csv_path="old_chip.csv",
    metadata={
        "chip_age_days": 180,
        "storage_temp": 20.0,  # Poor storage (room temp)
        "ri_medium": 1.3333,
        "visual_inspection": "slight discoloration",
        "notes": "Expired chip for failure mode analysis"
    }
)

# Test multiple sensors from same batch
for i in range(3):
    tdm.save_p_signal(
        detector="A",
        sensor_quality="good",
        chip_batch="DEF-2025-10",
        csv_path=f"batch_test_{i+1}.csv",
        metadata={
            "chip_age_days": 14,
            "storage_temp": 4.0,
            "ri_medium": 1.3333,
            "chip_number": f"#{i+1}",
            "notes": f"Batch consistency test #{i+1}/3"
        }
    )
```

### Query Training Data

```python
# Get all baseline S-signal measurements for Channel A
s_baselines = tdm.get_s_signal_data(detector="A", category="baseline")
print(f"Found {len(s_baselines)} baseline measurements")

for measurement in s_baselines:
    print(f"  {measurement['timestamp']}: {measurement['measurement_id']}")
    if 'warm_up_min' in measurement:
        print(f"    Warm-up: {measurement['warm_up_min']} min")

# Get excellent quality P-signal measurements
excellent_chips = tdm.get_p_signal_data(detector="A", quality="excellent")
print(f"\nFound {len(excellent_chips)} excellent quality measurements")

# Get all measurements from specific chip batch
batch_data = tdm.get_p_signal_data(
    detector="A",
    chip_batch="ABC-2025-10"
)

# View device statistics
stats = tdm.get_device_statistics()
print(f"\nTotal measurements: {stats['total_measurements']}")
print(f"S-signal: {stats['by_signal_type']['S']}")
print(f"P-signal: {stats['by_signal_type']['P']}")
```

### Export for Model Training

```python
# Export all data for detector A
tdm.export_training_dataset(
    output_file="detector_a_training_data.json",
    detector="A"
)

# Export only S-signal data (instrument characterization)
tdm.export_training_dataset(
    output_file="s_signal_training_data.json",
    signal_type="S"
)

# Export only excellent sensors for baseline model
tdm.export_training_dataset(
    output_file="excellent_sensors_baseline.json",
    signal_type="P",
    detector="A"
)
```

## 🖥️ Command Line Interface

### Initialize Device

```bash
# Create training data structure
python training_data_manager.py --device device_001 init
```

### Save Measurements

```bash
# Save S-signal (instrument characterization)
python training_data_manager.py --device device_001 save-s \
    --detector A \
    --category baseline \
    --csv "C:\Users\lucia\test.csv" \
    --warmup 15 \
    --temp 23.5

# Save P-signal (with sensor)
python training_data_manager.py --device device_001 save-p \
    --detector A \
    --quality excellent \
    --batch "ABC-2025-10" \
    --csv "fresh_chip.csv" \
    --chip-age 3 \
    --ri 1.3333
```

### Query Data

```bash
# Show statistics
python training_data_manager.py --device device_001 stats

# Query S-signal data
python training_data_manager.py --device device_001 query \
    --detector A \
    --signal S

# Query P-signal data by quality
python training_data_manager.py --device device_001 query \
    --detector A \
    --signal P \
    --quality excellent
```

### Export Dataset

```bash
# Export all training data
python training_data_manager.py --device device_001 export \
    --output training_dataset.json

# Export specific detector
python training_data_manager.py --device device_001 export \
    --output detector_a_only.json \
    --detector A \
    --signal P
```

## 📈 Phase 1 Workflow: Instrument Characterization

### Week 1: S-Signal Baseline (All Detectors)

```python
tdm = TrainingDataManager(device_id="device_001")

# After 15min warm-up, run baseline for each detector
for detector in ["A", "B", "C", "D"]:
    tdm.save_s_signal(
        detector=detector,
        category="baseline",
        csv_path=f"baseline_{detector}.csv",
        metadata={"warm_up_min": 15, "ambient_temp": 23.5}
    )

# Repeat 3x over the week (same conditions)
# This establishes instrument repeatability
```

**Goal**: Quantify instrument-only noise floor and repeatability

### Week 2: Thermal Characterization

```python
# Test different warm-up times
for warmup_time in [0, 5, 10, 15, 20]:
    tdm.save_s_signal(
        detector="A",
        category="thermal",
        csv_path=f"warmup_{warmup_time}min.csv",
        metadata={
            "warm_up_min": warmup_time,
            "test_sequence": "thermal_optimization"
        }
    )
```

**Goal**: Define optimal warm-up protocol

### Week 3: LED Optimization (Focus on Channel B)

```python
# Channel B has wavelength instability (1.01 nm)
# Test LED delay variations
for delay in [15, 20, 25, 30]:
    tdm.save_s_signal(
        detector="B",
        category="led_testing",
        csv_path=f"led_delay_{delay}ms.csv",
        metadata={
            "led_delay_ms": delay,
            "notes": "Optimizing wavelength stability"
        }
    )
```

**Goal**: Fix Channel B wavelength instability

### Week 4: P-Signal Reference (Excellent Sensors)

```python
# Use fresh, reference-quality chips
tdm.save_p_signal(
    detector="A",
    sensor_quality="excellent",
    chip_batch="REFERENCE-2025-10",
    csv_path="reference_chip_1.csv",
    metadata={
        "chip_age_days": 2,
        "storage_temp": 4.0,
        "ri_medium": 1.3333,
        "notes": "Reference baseline for peak tracking"
    }
)

# Repeat with 3-5 chips from same batch
# This separates chip variation from instrument variation
```

**Goal**: Establish peak tracking baseline with excellent sensors

## 🔮 Phase 2: Sensor Quality Characterization (Future)

Once all detectors achieve <15 RU p-p and <0.3 nm wavelength stability:

```python
# Test various sensor qualities
for quality in ["excellent", "good", "acceptable", "poor"]:
    tdm.save_p_signal(
        detector="A",
        sensor_quality=quality,
        chip_batch=f"BATCH-{quality}",
        csv_path=f"{quality}_sensor.csv",
        metadata={
            "ri_medium": 1.3333,
            "notes": f"Quality characterization: {quality}"
        }
    )
```

## 📊 Automatic Analysis Integration

All saved measurements automatically run `spectral_quality_analyzer.py`:

```python
# Analysis is saved alongside measurement
training_data/device_001/detector_A/s_signal/baseline/s_signal_20251022_143022/
├── measurement.csv          # Raw data
├── metadata.json           # Collection conditions
└── analysis.json           # Spectral quality analysis (auto-generated)
```

Access analysis in queries:

```python
measurements = tdm.get_s_signal_data(detector="A", category="baseline")

for meas in measurements:
    meas_path = Path(meas['measurement_path'])
    analysis_file = meas_path / "analysis.json"

    if analysis_file.exists():
        with open(analysis_file) as f:
            analysis = json.load(f)

        print(f"{meas['measurement_id']}:")
        print(f"  P2P: {analysis['channels']['A']['noise_peak_to_peak']:.2f} RU")
        print(f"  Wavelength std: {analysis['channels']['A']['wavelength_std']:.2f} nm")
        print(f"  Grade: {analysis['channels']['A']['overall_quality_grade']}")
```

## 🎯 Integration with Your Current Workflow

Add to `spr_data_acquisition.py` or similar:

```python
from training_data_manager import TrainingDataManager

class SPRMeasurement:
    def __init__(self):
        self.tdm = TrainingDataManager(device_id="device_001")

    def save_measurement_to_training_data(
        self,
        csv_path: str,
        signal_type: str,  # "S" or "P"
        detector: str,
        **kwargs
    ):
        """Save measurement to training database."""
        if signal_type == "S":
            self.tdm.save_s_signal(
                detector=detector,
                category=kwargs.get("category", "baseline"),
                csv_path=csv_path,
                metadata=kwargs
            )
        elif signal_type == "P":
            self.tdm.save_p_signal(
                detector=detector,
                sensor_quality=kwargs.get("sensor_quality", "good"),
                chip_batch=kwargs.get("chip_batch", "UNKNOWN"),
                csv_path=csv_path,
                metadata=kwargs
            )
```

## 🔧 Device Management (Multiple Instruments)

```python
# Lab with multiple instruments
devices = ["lab_a_unit_1", "lab_b_unit_1", "production_unit_5"]

for device_id in devices:
    tdm = TrainingDataManager(device_id=device_id)

    # Each device maintains separate training data
    stats = tdm.get_device_statistics()
    print(f"{device_id}: {stats['total_measurements']} measurements")

# Cross-device comparison
# Export each device's data, then compare instrument performance
```

## ✅ Benefits of This System

1. **Hierarchical Organization**: Device → Detector → Signal Type → Quality Level
2. **S/P Signal Separation**: Instrument-only vs sensor-dependent clearly separated
3. **Automatic Analysis**: Every measurement auto-analyzed and saved
4. **Rich Metadata**: Track storage, age, conditions for each measurement
5. **Easy Querying**: Find specific measurement types quickly
6. **Export for ML**: Consolidate data for model training
7. **Multi-Device Support**: Track multiple instruments independently
8. **Reproducibility**: Full context captured for every measurement

---

**Start collecting training data now with:**

```python
from training_data_manager import TrainingDataManager
tdm = TrainingDataManager(device_id="device_001")
tdm.save_s_signal("A", "baseline", "C:/Users/lucia/test.csv",
                  metadata={"warm_up_min": 15})
```
