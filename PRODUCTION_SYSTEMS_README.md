# SPR Application - Production Systems

## Overview

This document describes the three critical production systems implemented for the SPR application:

1. **Error Boundary System** - Comprehensive error handling with recovery mechanisms
2. **Structured Logging System** - Performance monitoring, security audit, and debugging
3. **Automated Testing Framework** - Unit tests, integration tests, and mock hardware

## Error Boundary System

### Features
- **Severity-based error handling** (LOW, MEDIUM, HIGH, CRITICAL)
- **Category-specific handling** (Hardware, Data Acquisition, Calibration, UI, etc.)
- **Automatic recovery mechanisms** with fallback strategies
- **User-friendly error messages** with technical logging
- **Graceful degradation** instead of application crashes

### Usage Examples

```python
# Hardware operations with automatic error protection
@safe_hardware_operation
def connect_spectrometer(self):
    return self.hardware_manager.connect_spectrometer()

# Data acquisition with recovery
@safe_data_operation
def acquire_spectrum(self):
    return self.spectrometer.get_spectrum()

# Calibration with error boundaries
@safe_calibration_operation
def perform_calibration(self):
    return self.calibrator.run_calibration()

# Manual error handling
from utils.error_boundary import error_boundary, ErrorCategory, ErrorSeverity

try:
    risky_operation()
except Exception as e:
    error_boundary.handle_error(
        error=e,
        category=ErrorCategory.HARDWARE,
        severity=ErrorSeverity.HIGH,
        context="Device connection",
        recovery_fn=lambda: self.reconnect_device(),
        user_message="Hardware connection lost. Attempting to reconnect..."
    )
```

## Structured Logging System

### Features
- **Multiple log levels** with automatic rotation
- **Performance monitoring** with timing measurements
- **Security audit trail** for hardware commands and configuration changes
- **JSON structured logs** for machine parsing
- **Color-coded console output** for development
- **Automated log rotation** to prevent disk space issues

### Log Files Created
- `spr_control.log` - Main application log (10MB, 5 backups)
- `spr_control_errors.log` - Errors only (5MB, 3 backups)
- `spr_control_structured.jsonl` - JSON structured logs (20MB, 3 backups)
- `spr_control_performance.log` - Performance metrics (5MB, 2 backups)
- `spr_control_security.log` - Security events (5MB, 5 backups)

### Usage Examples

```python
from utils.app_integration import get_logger, measure_performance, log_hardware_command

# Get a logger for your module
logger = get_logger(__name__)
logger.info("Module initialized successfully")

# Performance monitoring
with measure_performance("spectrum_acquisition"):
    spectrum = self.acquire_spectrum()

# Security logging for hardware commands
log_hardware_command(
    device="spectrometer",
    command="set_integration_time",
    parameters={"time_ms": 100}
)

# Performance decorator
@with_performance_monitoring("calibration_operation")
def run_calibration(self):
    return self.calibrator.calibrate()
```

## Automated Testing Framework

### Features
- **Mock hardware controllers** for testing without real hardware
- **Test data generators** for realistic test scenarios
- **Unit tests** for individual components
- **Integration tests** for component interaction
- **Performance tests** for optimization
- **Automated test discovery** and execution

### Running Tests

```bash
# Run all tests
python run_tests.py

# Run specific test categories
python run_tests.py --hardware    # Hardware tests only
python run_tests.py --unit        # Unit tests only
python run_tests.py --performance # Performance tests
python run_tests.py --verbose     # Detailed output

# Run specific test class
python -c "from tests.test_framework import TestRunner; TestRunner().run_specific_test('TestHardwareManager')"
```

### Test Structure

```python
from tests.test_framework import BaseTestCase, MockHardwareController

class MyTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        # Test setup with mock hardware available

    def test_hardware_connection(self):
        result = self.mock_hardware.connect()
        self.assertTrue(result)

    def test_data_processing(self):
        test_data = self.test_data.generate_measurement_data(100, 5)
        self.assertIn("wavelengths", test_data)
```

## Integration with Main Application

### Quick Start

1. **Initialize all systems** in your main application:

```python
from utils.app_integration import initialize_app_systems

# Initialize all production systems
config = {
    "version": "3.2.9",
    "hardware": {"spectrometer": "USB4000"},
    "logging_level": "INFO"
}

success = initialize_app_systems(config)
if not success:
    print("Failed to initialize production systems")
    sys.exit(1)
```

2. **Apply decorators** to existing methods:

```python
# Add to existing hardware methods
@safe_hardware_operation
def existing_connect_method(self):
    # ... existing code ...

# Add to data acquisition methods
@safe_data_operation
def existing_acquire_method(self):
    # ... existing code ...
```

3. **Add logging** to critical operations:

```python
from utils.app_integration import get_logger, log_config_change

logger = get_logger(__name__)

def update_configuration(self, new_config):
    old_config = self.get_current_config()
    self.apply_config(new_config)

    # Log the change for security audit
    log_config_change("main_application", {
        "old": old_config,
        "new": new_config
    })

    logger.info("Configuration updated successfully")
```

## File Structure

```
utils/
├── error_boundary.py       # Error boundary system
├── logging_system.py       # Structured logging
├── app_integration.py      # Integration layer
└── ...

tests/
├── test_framework.py       # Testing framework
└── ...

run_tests.py                # Test runner script
```

## Benefits

### Error Boundary System
- **Prevents application crashes** from hardware failures
- **Provides user-friendly error messages** instead of technical stacktraces
- **Enables automatic recovery** from common error conditions
- **Maintains application stability** during hardware disconnections

### Logging System
- **Comprehensive debugging information** with multiple log levels
- **Performance bottleneck identification** through timing measurements
- **Security compliance** with audit trails for all hardware commands
- **Automated log management** prevents disk space issues

### Testing Framework
- **Reliable testing** without requiring physical hardware
- **Regression prevention** through automated test execution
- **Performance monitoring** to detect degradation
- **Quality assurance** for new features and bug fixes

## Maintenance

### Log Management
- Logs automatically rotate to prevent disk space issues
- Review performance logs weekly for optimization opportunities
- Monitor security logs for unusual hardware command patterns

### Testing
- Run full test suite before any release
- Add new tests for any new features
- Update mock hardware as real hardware capabilities change

### Error Monitoring
- Review error logs daily for recurring issues
- Update recovery strategies based on common error patterns
- Monitor error rates for system health

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure all new files are in the correct directories
2. **Permission errors**: Check log directory write permissions
3. **Test failures**: Verify mock hardware setup and test data generation

### Getting Help

- Check log files in the `logs/` directory for detailed error information
- Run tests with `--verbose` flag for detailed test output
- Review error boundary history for recurring issues

This production system significantly improves the reliability, maintainability, and debuggability of the SPR application.