# Affilabs SPR Control System (ezControl-AI)

**Version 3.2.9** - Production Ready (October 2025)

## ⚡ Quick Start

### Prerequisites
- Windows 10/11
- Python 3.12+ (**REQUIRED** - enforced by launcher)
- USB4000 spectrometer with WinUSB drivers
- PicoP4SPR 4-channel controller

### Running the Application
```powershell
# PRIMARY METHOD (Recommended)
.\run_app_312.ps1

# Alternative
.\run_app_312.bat
```

The launcher will:
- ✅ Verify Python 3.12 is being used
- ✅ Activate the correct virtual environment (`.venv312`)
- ✅ Display Python version confirmation
- ✅ Start the application

---

## Overview

**ezControl-AI** is a production-ready Surface Plasmon Resonance (SPR) control system providing automated calibration, real-time measurements, and intelligent data processing for PicoP4SPR 4-channel devices with USB4000 spectrometer.

### Recent Major Fixes (October 2025)
1. ✅ **Saturation Issue Fixed**: Step 4 calibration now tests all channels at correct LED values
2. ✅ **Python 3.12 Enforcement**: 5-layer protection prevents version confusion
3. ✅ **Dark Noise Warnings Corrected**: Now uses detector profile baselines
4. ✅ **UI Cleanup**: Removed diagnostic viewer (development tool no longer needed)

See `CURRENT_STATUS.md` for complete details.

---

## Features

### Core Functionality
- **Real-time SPR data acquisition** from PicoP4SPR 4-channel devices
- **USB4000 spectrometer integration** via seabreeze (Ocean Direct API)
- **8-step automated calibration** with saturation prevention
- **Advanced data processing** with filtering and peak tracking
- **Temperature monitoring** and control
- **Pump management** (Cavro integration) for fluid handling
- **Kinetic measurements** with automated protocols
- **Real-time sensorgram display** for all 4 channels

### Production-Ready Architecture
- **Hardware Abstraction Layer (HAL)** for device independence
- **Detector-agnostic design** with profile-based configuration
- **Robust Python 3.12 enforcement** (5-layer protection)
- **Thread-safe operations** with proper resource management
- **Persistent calibration** with automatic validation
- **Comprehensive error handling** and logging

### Key Improvements (October 2025)
- ✅ **Fixed calibration saturation** - Step 4 tests all channels at predicted LED values
- ✅ **Python version enforcement** - Clear warnings and execution blocking if wrong version
- ✅ **Corrected dark noise warnings** - Uses detector profile baselines (3500 for USB4000)
- ✅ **Optimized polarizer threshold** - Reduced false alarms (1.33× ratio)
- ✅ **Streamlined UI** - Removed diagnostic viewer (development tool)

## Hardware Support

### Supported Devices
- **PicoP4SPR**: 4-channel SPR controller (Serial/COM communication)
  - LED control: 0-255 intensity per channel
  - Polarizer modes: P-mode (signal) / S-mode (reference)
  - Channels: a, b, c, d

- **USB4000**: Ocean Optics spectrometer (via seabreeze library)
  - Wavelength range: 200-1100 nm
  - Integration time: 1-65000 ms
  - Dynamic range: 65000 counts
  - Connection: USB with WinUSB drivers

- **Temperature sensors**: For environmental monitoring
- **Pump systems** (Cavro): For automated fluid handling

### Communication Protocols
- **Serial/COM**: For PicoP4SPR devices
- **USB/seabreeze**: For USB4000 spectrometers
- **USB**: For auxiliary devices

## Installation

### Requirements
- **Python 3.12+** (REQUIRED - Python 3.9/3.10/3.11 NOT supported)
- Windows 10/11
- WinUSB drivers for USB4000
- Serial drivers for PicoP4SPR

### Quick Setup
1. **Clone the repository**:
   ```bash
   git clone https://github.com/Ludo-affi/ezControl-AI.git
   cd ezControl-AI
   ```

2. **Create Python 3.12 virtual environment**:
   ```powershell
   py -3.12 -m venv .venv312
   .\.venv312\Scripts\Activate.ps1
   ```

3. **Install dependencies**:
   ```powershell
   pip install -r requirements.txt
   # or
   pip install PySide6 qasync pyqtgraph numpy scipy pyserial seabreeze
   ```

4. **Connect hardware**:
   - USB4000 spectrometer (USB)
   - PicoP4SPR controller (COM port)

5. **Launch application**:
   ```powershell
   .\run_app_312.ps1
   ```

### Python Version Enforcement
The application will **NOT RUN** on Python < 3.12. If wrong version detected:
- ❌ Application exits immediately with error dialog
- ❌ Terminal shows large ASCII warning banner
- ✅ Use `run_app_312.ps1` launcher to ensure correct version

See `PYTHON_312_REQUIREMENT.md` for details.

## Usage

### Starting the Application
```powershell
# RECOMMENDED: Use the launcher script
.\run_app_312.ps1

# Alternative launcher
.\run_app_312.bat

# Manual method (if needed)
.\.venv312\Scripts\Activate.ps1
python main/main.py
```

### First-Time Calibration
1. **Connect Hardware**: Ensure USB4000 and PicoP4SPR are connected
2. **Launch Application**: Use `run_app_312.ps1`
3. **Open Settings**: Click "Settings" button in toolbar
4. **Run Calibration**: Follow the 8-step calibration wizard
   - **Step 1**: Dark noise measurement (LED OFF)
   - **Step 2**: Dark measurement (LED ON, no polarizer)
   - **Step 3**: Polarizer ratio scan
   - **Step 4**: Binary search for integration time (**saturation-free**)
   - **Step 5**: Final integration time validation
   - **Step 6**: Reference spectrum measurement
   - **Step 7**: LED range validation
   - **Step 8**: Final system validation
5. **Wait for Completion**: Calibration takes ~5-10 minutes
6. **Start Measurement**: Return to Sensorgram view and click "Start"

### Live Mode Operation
- **Sensorgram View**: Real-time SPR signal for all 4 channels (a, b, c, d)
- **Acquisition Rate**: ~1.2 Hz (850ms per cycle)
- **Automatic Saturation Prevention**: System reduces LED if signal > 85%
- **Data Recording**: Click record button to log data
- **Emergency Stop**: Red button immediately halts acquisition

### UI Overview
- **Toolbar**: Settings, Recording, Advanced menu
- **Sidebar**: Kinetic measurement controls (toggle with sidebar button)
- **Main Display**: 4 view modes
  1. Sensorgram (real-time SPR tracking)
  2. Spectroscopy (raw spectra)
  3. Data Processing (processed data)
  4. Data Analysis (analysis tools)

# Save configuration
config.save_profile("my_experiment")
```

### Data Acquisition
```python
# Start measurement
app.start_measurement()

# Configure parameters
app.set_integration_time(50)  # ms
app.set_scan_count(10)

# Access real-time data
data = app.get_current_data()
spectrum = app.get_spectrum_data()
```

## Architecture

### Project Structure
```
ezControl-AI/
├── main/                 # Main application module
├── utils/               # Utility modules
│   ├── hal/            # Hardware Abstraction Layer
│   ├── config_manager.py
│   ├── data_buffer_manager.py
│   └── hardware_manager.py
├── ui/                  # User interface components
├── widgets/             # Custom Qt widgets
├── settings/            # Configuration files
└── tests/              # Test scripts
```

### Key Components

#### Hardware Abstraction Layer (HAL)
- **SPRControllerHAL**: Abstract interface for SPR controllers
- **SpectrometerHAL**: Abstract interface for spectrometers
- **HALFactory**: Factory for creating HAL instances
- **Device-specific implementations**: PicoP4SPR, USB4000, etc.

#### Configuration Management
- **ConfigurationManager**: Centralized configuration handling
- **Dataclass-based settings**: Type-safe configuration
- **Profile persistence**: Save/load experiment configurations
- **Validation**: Automatic parameter validation

#### Data Management
- **DataBufferManager**: Efficient data buffering
- **Real-time processing**: Live data filtering and analysis
- **Export capabilities**: Data export in various formats

## Development

### Code Quality
- **Type hints**: Full type annotation coverage
- **Error handling**: Comprehensive exception management
- **Logging**: Detailed logging for debugging
- **Testing**: Hardware and unit tests

### Testing
```bash
# Run hardware tests
python test_hal.py
python test_usb4000_hal.py
python quick_hardware_test.py

# Run unit tests
pytest tests/
```

### AI-Assisted Development
This project was developed with AI assistance, incorporating:
- **Intelligent code refactoring** for maintainability
- **Automated error detection** and correction
- **Performance optimization** suggestions
- **Documentation generation**

## Migration Notes

### From Previous Version
This represents a complete refactoring of the original SPR control system:

- **Phase 1-13**: HAL migration for all hardware components
- **Phase 14**: Code cleaning and organization
- **Phase 15**: Configuration management refactoring
- **Phase 16-17**: Dependency resolution and runtime fixes

### Key Improvements
- **Modern Python practices**: Type hints, dataclasses, context managers
- **Better error handling**: Comprehensive exception management
- **Improved performance**: Optimized data processing
- **Enhanced maintainability**: Modular architecture
- **Hardware independence**: HAL abstraction layer

## Configuration
## Troubleshooting

### USB4000 Not Detected
- Check Device Manager for "USB4000" device
- Verify WinUSB drivers installed
- Try unplugging/replugging USB cable
- Restart application
- Check seabreeze backend: `python -c "import seabreeze; seabreeze.list_devices()"`

### Python Version Errors
- **ALWAYS use `run_app_312.ps1` launcher**
- Check terminal banner shows "Python 3.12.10" or higher
- If wrong version detected, app will EXIT immediately
- Do NOT try to run with Python 3.9/3.10/3.11 (typing incompatibilities)

### Calibration Issues
- **Saturation during Step 4**: ✅ **FIXED** - Update to latest version
- **Dark noise warnings**: Ensure LEDs are OFF during Step 1
- **Polarizer ratio low**: Check polarizer alignment (warning threshold 1.33×)
- **Integration time too long**: Reduce LED intensity or check sample alignment

### Slow Acquisition
- Normal: ~60ms per spectrum with typical integration times
- Expected cycle time: ~850ms (12 spectra: 4 channels × 3 acquisitions)
- Rate: ~1.2 Hz sustained
- If slower: Check USB connection, system load, or integration time settings

### Application Crashes
- Check logs in terminal output
- Verify all hardware connections
- Ensure no other software is using COM port or USB4000
- Kill residual Python processes: `Stop-Process -Name python -Force`

## Contributing

### Development Setup
1. Fork the repository
2. Create a feature branch
3. Install development dependencies: `pdm install --dev`
4. Make changes with proper testing
5. Submit pull request

### Code Standards
- Follow PEP 8 style guidelines
- Add type hints for all functions
- Include docstrings for public APIs
- Write tests for new functionality
- Update documentation as needed

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- **AI-Enhanced Development**: This project was developed with advanced AI assistance
- **Ocean Optics**: For USB4000 spectrometer support
- **Qt Framework**: For the user interface
- **Python Community**: For excellent libraries and tools

## Support

For hardware issues:
- Check device connections and drivers
- Run hardware test scripts
- Verify Device Manager recognition

For software issues:
- Check logs for error details
- Verify Python environment setup
- Test with minimal configuration

## Version History

- **v3.2.9**: AI-enhanced refactoring with modern architecture
- **Previous versions**: Legacy SPR control system

---

**ezControl-AI** - Advanced SPR Control with AI Enhancement