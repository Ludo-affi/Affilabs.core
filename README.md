# Affilabs SPR Control System

**Version 0.1.0** - The Core

## Overview

**Affilabs** is a production-ready Surface Plasmon Resonance (SPR) control system providing automated calibration, real-time measurements, and intelligent data processing. This release establishes the core foundation for advanced SPR analysis and represents the culmination of extensive refinement in hardware abstraction, polarizer management, and detector-agnostic design.

Built with AI-enhanced development practices, Affilabs combines robust hardware control with modern software architecture to deliver a reliable, user-friendly SPR measurement platform.

## Features

### Core Functionality
- **Real-time SPR data acquisition** from PicoP4SPR devices
- **Spectrometer integration** with USB4000 via Ocean Direct API
- **Advanced data processing** with filtering and calibration
- **Temperature monitoring** and control
- **Pump management** for fluid handling
- **Kinetic measurements** with automated protocols

### Modern Architecture
- **Hardware Abstraction Layer (HAL)** for device independence
- **Configuration Management System** with dataclass-based settings
- **Data Buffer Management** for efficient data handling
- **Modular calibration system** with profile persistence
- **Thread-safe operations** with proper resource management

### AI Enhancements
- **Intelligent configuration management** with automatic validation
- **Smart error handling** and recovery mechanisms
- **Optimized data processing** algorithms
- **Enhanced user interface** responsiveness

## Hardware Support

### Supported Devices
- **PicoP4SPR**: 4-channel SPR controller (Serial/USB communication)
- **USB4000**: Ocean Optics spectrometer (WinUSB/Ocean Direct API)
- **KNX systems**: For advanced kinetic measurements
- **Temperature sensors**: For environmental monitoring
- **Pump systems**: For automated fluid handling

### Communication Protocols
- **Serial/COM**: For PicoP4SPR devices
- **WinUSB/Ocean Direct**: For USB4000 spectrometers (VISA-free)
- **USB**: For various auxiliary devices

## Installation

### Requirements
- Python 3.11+
- Windows 10/11
- WinUSB drivers for USB4000
- Serial drivers for PicoP4SPR

### Dependencies
```bash
# Core dependencies
pip install PySide6 qasync pyqtgraph
pip install numpy scipy
pip install pyserial
pip install oceandirect

# Development dependencies  
pip install pdm pytest mypy
```

### Setup
1. Clone the repository
2. Install dependencies: `pdm install`
3. Connect hardware devices
4. Run hardware test: `python quick_hardware_test.py`
5. Launch application: `python main/main.py`

## Usage

### Quick Start
1. **Connect Hardware**: Ensure PicoP4SPR and USB4000 are connected
2. **Test Connections**: Run `python quick_hardware_test.py`
3. **Launch Application**: Run `python main/main.py`
4. **Configure Settings**: Use the configuration manager for device setup
5. **Start Measurement**: Begin SPR data acquisition

### Configuration
The system uses a sophisticated configuration management system:

```python
from utils.config_manager import ConfigurationManager

# Initialize configuration
config = ConfigurationManager()

# Device settings
config.device.integration_time = 50  # milliseconds
config.device.num_scans = 10

# Calibration settings
config.calibration.auto_calibrate = True
config.calibration.reference_channels = ['a', 'b']

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

### Device Configuration
```python
# Device settings
device_config = DeviceConfiguration(
    integration_time=50,
    num_scans=10,
    selected_channels=['a', 'b', 'c', 'd'],
    led_intensity=75
)
```

### Calibration Configuration
```python
# Calibration settings
cal_config = CalibrationConfiguration(
    auto_calibrate=True,
    reference_channels=['a', 'b'],
    dark_subtraction=True,
    wavelength_calibration=True
)
```

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