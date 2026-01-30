# Detector-Agnostic Processing Pipeline Implementation

## Summary

The data processing pipeline is now **detector-agnostic** - it automatically detects the detector type and uses the appropriate wavelength ranges for peak finding. No more hardcoded wavelength ranges!

## What Changed

### 1. New Detector Configuration System ([affilabs/utils/detector_config.py](affilabs/utils/detector_config.py))

Created a centralized detector database that maps detector serial numbers to their characteristics:

- **Phase Photonics (ST series)**: 570-720nm valid range
- **Ocean Optics USB4000**: 560-720nm valid range  
- **Ocean Optics Flame-T**: 560-720nm valid range

The system automatically identifies detector type from serial number prefix:
- `ST*` → Phase Photonics
- `USB4*` → USB4000
- `FLMT*` → Flame-T

### 2. Updated Processing Pipelines

All peak finding pipelines now accept detector information via kwargs:

#### Fourier Pipeline ([affilabs/utils/pipelines/fourier_pipeline.py](affilabs/utils/pipelines/fourier_pipeline.py))
- ❌ Before: Hardcoded `spr_mask = (wavelengths >= 560.0) & (wavelengths <= 720.0)`
- ✅ After: `spr_min, spr_max = get_spr_wavelength_range(detector_serial, detector_type)`

#### Consensus Pipeline ([affilabs/utils/pipelines/consensus_pipeline.py](affilabs/utils/pipelines/consensus_pipeline.py))
- ❌ Before: Hardcoded `mask = (wavelengths >= 600) & (wavelengths <= 690)`
- ✅ After: Detector-aware range from `get_spr_wavelength_range()`

#### Direct ArgMin Pipeline ([affilabs/utils/pipelines/direct_argmin_pipeline.py](affilabs/utils/pipelines/direct_argmin_pipeline.py))
- ❌ Before: Hardcoded `search_min = 560`, `search_max = 720`
- ✅ After: Runtime detection from detector serial/type

### 3. SpectrumProcessor Updates ([affilabs/utils/spectrum_processor.py](affilabs/utils/spectrum_processor.py))

- Added `detector_serial` and `detector_type` parameters to `__init__`
- Added `set_detector_info()` method to update detector info dynamically
- Automatically passes detector info to all pipeline `find_resonance_wavelength()` calls

### 4. Main Application Integration ([main.py](main.py))

The `_on_hardware_connected()` method now:
1. Extracts detector serial from `hardware_mgr.usb.serial_number`
2. Updates all spectrum processors with detector info
3. Updates sidebar plot ranges based on detector type

### 5. Settings Documentation ([affilabs/settings/settings.py](affilabs/settings/settings.py))

Updated to mark hardcoded constants as DEPRECATED:
```python
# DEPRECATED: Use detector_config.get_spr_wavelength_range()
MIN_WAVELENGTH = 560  
MAX_WAVELENGTH = 720
CONSENSUS_SEARCH_RANGE = (600, 720)  # DEPRECATED
```

## How It Works

### Automatic Detection Flow

```
1. Hardware connects
   └─> hardware_mgr.usb.serial_number = "ST00012"

2. main._on_hardware_connected(status)
   └─> spectrum_processor.set_detector_info(detector_serial="ST00012")
   └─> sidebar.set_detector_type("PhasePhotonics")

3. During acquisition
   └─> pipeline.find_resonance_wavelength(
           transmission=...,
           wavelengths=...,
           detector_serial="ST00012"  ← Passed automatically
       )

4. Pipeline uses detector-specific range
   └─> get_spr_wavelength_range("ST00012")
   └─> Returns (570.0, 720.0) for Phase Photonics
   └─> Peak finding uses correct wavelength mask
```

### API Usage Examples

```python
from affilabs.utils.detector_config import get_spr_wavelength_range

# By serial number
spr_min, spr_max = get_spr_wavelength_range(serial_number="ST00012")
# Returns: (570.0, 720.0)

# By detector type
spr_min, spr_max = get_spr_wavelength_range(detector_type="PhasePhotonics")
# Returns: (570.0, 720.0)

# Default fallback (USB4000)
spr_min, spr_max = get_spr_wavelength_range()
# Returns: (560.0, 720.0)
```

## Benefits

✅ **No more hardcoded wavelength ranges** - system adapts to detector automatically  
✅ **Correct peak finding** - Phase Photonics uses 570nm start (not 560nm)  
✅ **Backward compatible** - defaults to USB4000 for unknown detectors  
✅ **Easy to extend** - add new detectors by updating DETECTOR_DATABASE  
✅ **Consistent everywhere** - UI plots and processing use same ranges  

## Testing

Run the test suite to verify:
```bash
python test_detector_config.py
```

Expected output:
```
✓ Phase Photonics detection: ST00012 -> 570.0-720.0nm
✓ USB4000 detection: USB4H14526 -> 560.0-720.0nm
✓ Detector type string detection works
✓ Default fallback to USB4000 works
✓ Fourier pipeline with Phase Photonics
✓ Direct ArgMin pipeline with Phase Photonics
✓ Consensus pipeline with USB4000
```

## Files Modified

1. **New File**: `affilabs/utils/detector_config.py` - Detector database
2. **Updated**: `affilabs/utils/pipelines/fourier_pipeline.py` - Detector-aware masking
3. **Updated**: `affilabs/utils/pipelines/consensus_pipeline.py` - Detector-aware masking
4. **Updated**: `affilabs/utils/pipelines/direct_argmin_pipeline.py` - Detector-aware search range
5. **Updated**: `affilabs/utils/spectrum_processor.py` - Detector info tracking
6. **Updated**: `main.py` - Hardware connection detector info propagation
7. **Updated**: `affilabs/settings/settings.py` - Deprecated hardcoded constants
8. **New File**: `test_detector_config.py` - Test suite

## Adding New Detectors

To add a new detector, update `DETECTOR_DATABASE` in `detector_config.py`:

```python
DETECTOR_DATABASE = {
    "NewDetector": DetectorCharacteristics(
        name="New Detector Model",
        serial_prefix="NEWDET",  # Serial starts with "NEWDET"
        wavelength_min=550.0,
        wavelength_max=730.0,
        spr_wavelength_min=560.0,
        spr_wavelength_max=720.0,
        max_counts=32768,
        pixels=2048,
    ),
    # ... existing detectors ...
}
```

The system will automatically recognize serials starting with "NEWDET" and use the correct wavelength ranges.

## Migration Notes

No breaking changes - the system maintains backward compatibility:
- Unknown detectors default to USB4000 ranges (560-720nm)
- Existing code continues to work without modification
- Hardcoded ranges in settings.py remain for legacy code

## Next Steps

Consider extending this system to:
- [ ] Auto-detect detector type from spectral response
- [ ] Store detector calibration data in detector_config
- [ ] Add detector-specific baseline correction parameters
- [ ] Implement detector health monitoring based on characteristics
