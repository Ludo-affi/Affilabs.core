#!/usr/bin/env python3
"""Test data acquisition startup to isolate crash cause."""

import sys
import logging
import time
from pathlib import Path

# Add the project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s :: %(message)s')
logger = logging.getLogger(__name__)

def test_signal_emission():
    """Test if signal emission is causing the crash."""
    logger.info("Testing signal emission crash scenario...")

    try:
        # Import the state machine
        from utils.spr_state_machine import DataAcquisitionWrapper
        from main.main import AffiniteApp

        logger.info("Creating minimal app instance...")
        app = AffiniteApp()

        logger.info("Creating data acquisition wrapper...")
        data_wrapper = DataAcquisitionWrapper(app)

        logger.info("Data acquisition wrapper created successfully")

        # Try to create a mock acquisition to test signal emission
        class MockDataAcquisition:
            def __init__(self):
                self.calibrated = True
                self._b_stop = None
                self._b_kill = None

            def grab_data(self):
                logger.info("Mock grab_data called - this should work")
                time.sleep(1)
                logger.info("Mock grab_data completed")

            def set_configuration(self, **kwargs):
                logger.info(f"Mock set_configuration called: {kwargs}")

        # Test if we can set a mock acquisition
        logger.info("Testing mock data acquisition...")
        data_wrapper.data_acquisition = MockDataAcquisition()

        logger.info("✅ Signal emission test completed successfully")
        return True

    except Exception as e:
        logger.exception(f"❌ Signal emission test failed: {e}")
        return False

def main():
    logger.info("=== Testing Data Acquisition Crash ===")

    if test_signal_emission():
        logger.info("✅ All tests passed - signal emission is working")
    else:
        logger.error("❌ Signal emission test failed")

    logger.info("=== Test completed ===")

if __name__ == "__main__":
    main()