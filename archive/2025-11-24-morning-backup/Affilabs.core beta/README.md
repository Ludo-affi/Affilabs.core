# AffiLabs.core Beta

Clean, simplified version of the SPR control software.

## Quick Start

**Windows:**
```
run.bat
```

**Command Line:**
```
python main_simplified.py
```

## What's Included

This folder contains only the essential files for the simplified application:

- `main_simplified.py` - Main application entry point
- `LL_UI_v1_0.py` - Modern UI interface
- `config.py` - Configuration settings
- `afterglow_correction.py` - Afterglow correction module
- `core/` - Core managers (hardware, data acquisition, recording, kinetic, buffers, FMEA)
- `utils/` - Utility modules (logger, signal processing, calibration, etc.)
- `widgets/` - UI widgets
- `ui/` - UI definition files
- `settings/` - Application settings

## Features

- **Modern UI** by Dr. Live
- **Hardware Management** - SPR controllers, kinetics, pumps, spectrometers
- **Data Acquisition** - Batched spectrum processing (4x faster)
- **Afterglow Correction** - LED phosphor afterglow compensation
- **FMEA Tracking** - Failure mode analysis and mitigation
- **Live Data Processing** - Real-time signal processing with quality monitoring
- **Recording** - Session data export
- **Kinetic Operations** - Multi-channel kinetic measurements

## Recent Improvements

### Performance Optimizations
- ✅ Pandas operations optimized (50-100x faster logging)
- ✅ Batched spectrum acquisition (75% fewer processing calls)
- ✅ Wavelength index caching (200ms saved per cycle)

### Quality & Monitoring
- ✅ Afterglow validation system with LED type tracking
- ✅ FMEA tracker for cohesive failure monitoring
- ✅ Cross-phase correlation (calibration → afterglow → live data)
- ✅ Scenario-based mitigation strategies

## Version

AffiLabs.core v4.0 (Beta)
