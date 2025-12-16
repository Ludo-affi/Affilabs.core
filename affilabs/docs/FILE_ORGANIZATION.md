# Affilabs.core Beta - File Organization

## Structure

```
Affilabs.core beta/
├── main_simplified.py          # Main application launcher
├── LL_UI_v1_0.py              # Modern UI by Dr. Live
├── config.py                  # Configuration constants
├── afterglow_correction.py    # Afterglow correction module
├── run.bat                    # Windows launcher script
├── README.md                  # Documentation
│
├── core/                      # Core management modules
│   ├── data_acquisition_manager.py    # Spectrum acquisition with batching
│   ├── data_buffer_manager.py         # Data buffering
│   ├── fmea_integration.py            # FMEA integration helpers
│   ├── fmea_tracker.py                # Failure mode tracking
│   ├── hardware_manager.py            # Hardware coordination
│   ├── kinetic_manager.py             # Kinetic operations
│   └── recording_manager.py           # Session recording
│
├── settings/                  # Application settings
│   └── settings.py
│
├── utils/                     # Utility modules
│   ├── logger.py                      # Logging
│   ├── spr_signal_processing.py      # Signal processing
│   ├── session_quality_monitor.py    # Quality monitoring
│   ├── device_configuration.py       # Device config
│   ├── led_calibration.py            # LED calibration
│   ├── usb4000_wrapper.py            # Spectrometer driver
│   ├── controller.py                 # SPR controller interface
│   ├── cavro_pump.py                 # Pump control
│   ├── data_exporter.py              # Data export
│   ├── spectrum_processor.py         # Spectrum processing
│   ├── temporal_filter.py            # Temporal filtering
│   ├── hal/                          # Hardware abstraction
│   │   ├── adapters.py
│   │   ├── controller_hal.py
│   │   └── interfaces.py
│   └── pipelines/                    # Processing pipelines
│
├── widgets/                   # UI widgets
│   ├── mainwindow.py                 # Main window
│   ├── segment_dataframe.py          # Segment management
│   ├── advanced.py                   # Advanced settings
│   └── analysis.py                   # Analysis tools
│
└── ui/                        # UI definitions
    ├── ui_*.py                       # Generated UI files
    └── img/                          # Images and icons
```

## What Was NOT Copied

To keep the codebase clean, the following were excluded:

- `Old software/main/` - Old main.py (not needed for simplified version)
- `Old software/Phase Photonics Modifications/` - OEM-specific modifications
- `Old software/hardware/` - Duplicate hardware drivers (kept in utils/)
- Test scripts and analysis notebooks
- Documentation and markdown files from Old software
- Calibration data and session files (these are in root level)

## Benefits

1. **Clean Separation** - Beta version independent from old code
2. **Minimal Dependencies** - Only essential files included
3. **Root Level** - Easy to find and launch
4. **All Recent Improvements** - Includes batching, FMEA, optimizations
5. **Ready to Run** - Use `run.bat` or `python main_simplified.py`

## Integration Status

✅ **Included & Working:**
- Batched spectrum acquisition (4 spectra minimum)
- Pandas optimizations (50-100x faster)
- Afterglow correction with validation
- FMEA tracker (ready for integration)
- Wavelength index caching
- Session quality monitoring

⚠️ **Ready but Not Integrated:**
- FMEA tracker needs to be connected to:
  - LED calibration events
  - Afterglow validation checks
  - Live data quality monitoring

See `core/fmea_integration.py` for integration examples.

## Migration Path

If you want to add features from "Old software":

1. Check if the module exists in this beta folder
2. If not, copy it from "Old software/" to the corresponding location
3. Test that imports work
4. Update any path references if needed

The simplified structure makes it easy to add only what you need without carrying legacy code.
