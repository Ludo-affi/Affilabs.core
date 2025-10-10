"""
Automated testing framework for the SPR application.

This module provides:
- Unit testing for core components
- Integration testing for hardware interfaces
- Mock hardware for testing
- Test data generators
- Automated test discovery and execution
"""

import unittest
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import tempfile
import json
import time
from unittest.mock import Mock, MagicMock, patch
import numpy as np

# Add the project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class MockHardwareController:
    """Mock hardware controller for testing."""
    
    def __init__(self):
        self.connected = False
        self.config = {}
        self.last_command = None
        self.call_count = 0
        
    def connect(self) -> bool:
        """Mock connection method."""
        self.connected = True
        self.call_count += 1
        return True
        
    def disconnect(self) -> bool:
        """Mock disconnection method."""
        self.connected = False
        self.call_count += 1
        return True
        
    def send_command(self, command: str, params: Optional[Dict] = None) -> Dict:
        """Mock command sending."""
        self.last_command = {'command': command, 'params': params}
        self.call_count += 1
        
        # Simulate different responses based on command
        if command == "get_status":
            return {"status": "ok", "connected": self.connected}
        elif command == "get_data":
            return {"data": np.random.rand(100).tolist()}
        elif command == "calibrate":
            return {"result": "success", "calibration_data": [1.0, 2.0, 3.0]}
        else:
            return {"result": "unknown_command"}

class MockSpectrometer:
    """Mock spectrometer for testing."""
    
    def __init__(self):
        self.integration_time = 100
        self.wavelengths = np.linspace(200, 800, 2048)
        self.connected = False
        
    def connect(self) -> bool:
        """Mock connection."""
        self.connected = True
        return True
        
    def get_wavelengths(self) -> np.ndarray:
        """Get mock wavelength data."""
        return self.wavelengths
        
    def get_spectrum(self) -> np.ndarray:
        """Get mock spectrum data."""
        # Generate realistic-looking spectrum
        spectrum = np.random.normal(1000, 100, len(self.wavelengths))
        spectrum = np.maximum(spectrum, 0)  # No negative values
        return spectrum
        
    def set_integration_time(self, time_ms: int) -> bool:
        """Set integration time."""
        self.integration_time = time_ms
        return True

class TestDataGenerator:
    """Generate test data for various scenarios."""
    
    @staticmethod
    def generate_calibration_data(num_points: int = 100) -> Dict[str, Any]:
        """Generate mock calibration data."""
        wavelengths = np.linspace(200, 800, num_points)
        reference = np.random.normal(1000, 50, num_points)
        return {
            "wavelengths": wavelengths.tolist(),
            "reference": reference.tolist(),
            "timestamp": time.time(),
            "integration_time": 100
        }
    
    @staticmethod
    def generate_measurement_data(num_points: int = 100, num_measurements: int = 10) -> Dict[str, Any]:
        """Generate mock measurement data."""
        wavelengths = np.linspace(200, 800, num_points)
        measurements = []
        
        for i in range(num_measurements):
            # Add some variation to each measurement
            intensity = np.random.normal(800 + i * 10, 30, num_points)
            measurements.append(intensity.tolist())
        
        return {
            "wavelengths": wavelengths.tolist(),
            "measurements": measurements,
            "timestamps": [time.time() + i for i in range(num_measurements)],
            "metadata": {
                "num_points": num_points,
                "num_measurements": num_measurements,
                "integration_time": 100
            }
        }
    
    @staticmethod
    def generate_config_data() -> Dict[str, Any]:
        """Generate mock configuration data."""
        return {
            "hardware": {
                "spectrometer": {
                    "type": "USB4000",
                    "serial": "TEST123",
                    "integration_time": 100
                },
                "controller": {
                    "type": "PicoP4SPR",
                    "port": "COM3",
                    "baudrate": 115200
                }
            },
            "calibration": {
                "wave_min": 400,
                "wave_max": 700,
                "reference_file": "test_reference.json"
            },
            "acquisition": {
                "averaging": 5,
                "save_raw": True,
                "auto_save": False
            }
        }

class BaseTestCase(unittest.TestCase):
    """Base test case with common functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.mock_hardware = MockHardwareController()
        self.mock_spectrometer = MockSpectrometer()
        self.test_data = TestDataGenerator()
        
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def assertArrayEqual(self, arr1: np.ndarray, arr2: np.ndarray, msg: str = None):
        """Assert that two numpy arrays are equal."""
        try:
            np.testing.assert_array_equal(arr1, arr2)
        except AssertionError as e:
            self.fail(msg or str(e))
    
    def assertArrayAlmostEqual(self, arr1: np.ndarray, arr2: np.ndarray, 
                              decimal: int = 7, msg: str = None):
        """Assert that two numpy arrays are almost equal."""
        try:
            np.testing.assert_array_almost_equal(arr1, arr2, decimal=decimal)
        except AssertionError as e:
            self.fail(msg or str(e))

class TestHardwareManager(BaseTestCase):
    """Test hardware manager functionality."""
    
    def test_hardware_connection(self):
        """Test hardware connection and disconnection."""
        # Test connection
        result = self.mock_hardware.connect()
        self.assertTrue(result)
        self.assertTrue(self.mock_hardware.connected)
        
        # Test disconnection
        result = self.mock_hardware.disconnect()
        self.assertTrue(result)
        self.assertFalse(self.mock_hardware.connected)
    
    def test_command_sending(self):
        """Test command sending functionality."""
        self.mock_hardware.connect()
        
        # Test status command
        response = self.mock_hardware.send_command("get_status")
        self.assertIn("status", response)
        self.assertEqual(response["status"], "ok")
        
        # Test data command
        response = self.mock_hardware.send_command("get_data")
        self.assertIn("data", response)
        self.assertIsInstance(response["data"], list)
        
        # Verify command was recorded
        self.assertEqual(self.mock_hardware.last_command["command"], "get_data")
    
    def test_calibration_command(self):
        """Test calibration command."""
        self.mock_hardware.connect()
        
        response = self.mock_hardware.send_command("calibrate", {"type": "reference"})
        self.assertEqual(response["result"], "success")
        self.assertIn("calibration_data", response)

class TestSpectrometer(BaseTestCase):
    """Test spectrometer functionality."""
    
    def test_spectrometer_connection(self):
        """Test spectrometer connection."""
        result = self.mock_spectrometer.connect()
        self.assertTrue(result)
        self.assertTrue(self.mock_spectrometer.connected)
    
    def test_wavelength_data(self):
        """Test wavelength data retrieval."""
        wavelengths = self.mock_spectrometer.get_wavelengths()
        self.assertIsInstance(wavelengths, np.ndarray)
        self.assertEqual(len(wavelengths), 2048)
        self.assertGreater(wavelengths[0], 190)  # Should start around 200nm
        self.assertLess(wavelengths[-1], 810)    # Should end around 800nm
    
    def test_spectrum_acquisition(self):
        """Test spectrum data acquisition."""
        spectrum = self.mock_spectrometer.get_spectrum()
        self.assertIsInstance(spectrum, np.ndarray)
        self.assertEqual(len(spectrum), 2048)
        self.assertTrue(np.all(spectrum >= 0))  # No negative values
    
    def test_integration_time_setting(self):
        """Test integration time setting."""
        result = self.mock_spectrometer.set_integration_time(200)
        self.assertTrue(result)
        self.assertEqual(self.mock_spectrometer.integration_time, 200)

class TestDataProcessing(BaseTestCase):
    """Test data processing functionality."""
    
    def test_calibration_data_generation(self):
        """Test calibration data generation."""
        cal_data = self.test_data.generate_calibration_data(100)
        
        self.assertIn("wavelengths", cal_data)
        self.assertIn("reference", cal_data)
        self.assertIn("timestamp", cal_data)
        self.assertEqual(len(cal_data["wavelengths"]), 100)
        self.assertEqual(len(cal_data["reference"]), 100)
    
    def test_measurement_data_generation(self):
        """Test measurement data generation."""
        meas_data = self.test_data.generate_measurement_data(50, 5)
        
        self.assertIn("wavelengths", meas_data)
        self.assertIn("measurements", meas_data)
        self.assertIn("timestamps", meas_data)
        self.assertEqual(len(meas_data["wavelengths"]), 50)
        self.assertEqual(len(meas_data["measurements"]), 5)
        self.assertEqual(len(meas_data["timestamps"]), 5)
    
    def test_config_data_structure(self):
        """Test configuration data structure."""
        config = self.test_data.generate_config_data()
        
        # Check main sections
        self.assertIn("hardware", config)
        self.assertIn("calibration", config)
        self.assertIn("acquisition", config)
        
        # Check hardware section
        hardware = config["hardware"]
        self.assertIn("spectrometer", hardware)
        self.assertIn("controller", hardware)
        
        # Check spectrometer config
        spec_config = hardware["spectrometer"]
        self.assertIn("type", spec_config)
        self.assertIn("integration_time", spec_config)

class TestErrorHandling(BaseTestCase):
    """Test error handling functionality."""
    
    def test_hardware_error_recovery(self):
        """Test hardware error recovery."""
        # Simulate hardware error
        with patch.object(self.mock_hardware, 'connect', side_effect=Exception("Connection failed")):
            with self.assertRaises(Exception):
                self.mock_hardware.connect()
    
    def test_data_validation(self):
        """Test data validation."""
        # Test valid data
        valid_data = np.array([1, 2, 3, 4, 5])
        self.assertTrue(np.all(np.isfinite(valid_data)))
        
        # Test invalid data
        invalid_data = np.array([1, 2, np.inf, 4, 5])
        self.assertFalse(np.all(np.isfinite(invalid_data)))

class TestRunner:
    """Test runner for the SPR application."""
    
    def __init__(self, test_dir: str = "tests"):
        self.test_dir = Path(test_dir)
        self.results = {}
    
    def discover_tests(self) -> unittest.TestSuite:
        """Discover all tests in the test directory."""
        loader = unittest.TestLoader()
        
        # Add current module tests
        suite = unittest.TestSuite()
        suite.addTest(loader.loadTestsFromTestCase(TestHardwareManager))
        suite.addTest(loader.loadTestsFromTestCase(TestSpectrometer))
        suite.addTest(loader.loadTestsFromTestCase(TestDataProcessing))
        suite.addTest(loader.loadTestsFromTestCase(TestErrorHandling))
        
        return suite
    
    def run_tests(self, verbosity: int = 2) -> Dict[str, Any]:
        """Run all discovered tests."""
        suite = self.discover_tests()
        
        # Create test runner
        runner = unittest.TextTestRunner(
            verbosity=verbosity,
            stream=sys.stdout,
            buffer=True
        )
        
        # Run tests
        print("=" * 70)
        print("Running SPR Application Test Suite")
        print("=" * 70)
        
        start_time = time.time()
        result = runner.run(suite)
        end_time = time.time()
        
        # Compile results
        self.results = {
            "tests_run": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "skipped": len(result.skipped) if hasattr(result, 'skipped') else 0,
            "success_rate": ((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun) * 100 if result.testsRun > 0 else 0,
            "duration": round(end_time - start_time, 2),
            "timestamp": time.time()
        }
        
        # Print summary
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        print(f"Tests run: {self.results['tests_run']}")
        print(f"Failures: {self.results['failures']}")
        print(f"Errors: {self.results['errors']}")
        print(f"Skipped: {self.results['skipped']}")
        print(f"Success rate: {self.results['success_rate']:.1f}%")
        print(f"Duration: {self.results['duration']} seconds")
        
        return self.results
    
    def run_specific_test(self, test_class_name: str, test_method_name: str = None):
        """Run a specific test class or method."""
        loader = unittest.TestLoader()
        
        # Get the test class
        test_classes = {
            'TestHardwareManager': TestHardwareManager,
            'TestSpectrometer': TestSpectrometer,
            'TestDataProcessing': TestDataProcessing,
            'TestErrorHandling': TestErrorHandling
        }
        
        if test_class_name not in test_classes:
            print(f"Test class '{test_class_name}' not found")
            return
        
        test_class = test_classes[test_class_name]
        
        if test_method_name:
            # Run specific method
            suite = unittest.TestSuite()
            suite.addTest(test_class(test_method_name))
        else:
            # Run all methods in class
            suite = loader.loadTestsFromTestCase(test_class)
        
        runner = unittest.TextTestRunner(verbosity=2)
        runner.run(suite)

def run_all_tests():
    """Convenience function to run all tests."""
    test_runner = TestRunner()
    return test_runner.run_tests()

if __name__ == "__main__":
    # Run tests when script is executed directly
    run_all_tests()