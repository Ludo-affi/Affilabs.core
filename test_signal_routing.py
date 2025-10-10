#!/usr/bin/env python3
"""Test signal routing to debug the SignalEmitter blocking issue."""

import sys
import logging
from typing import Any

# Set up logging to see what's happening
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s :: %(message)s')
logger = logging.getLogger(__name__)

class MockSignalEmitter:
    """Mock SignalEmitter for testing."""
    def emit(self, *args: Any) -> None:
        logger.info(f"MockSignalEmitter.emit called with: {[type(arg).__name__ for arg in args]}")

class MockDataAcquisition:
    """Mock data acquisition to test signal calling."""

    def __init__(self, update_signal):
        self.update_live_signal = update_signal

    def sensorgram_data(self):
        """Return mock sensorgram data."""
        return {"time": [1, 2, 3], "intensity": [100, 200, 300]}

    def emit_data_correctly(self):
        """Test correct data emission."""
        logger.info("Testing CORRECT emission: self.update_live_signal.emit(self.sensorgram_data())")
        data = self.sensorgram_data()
        logger.info(f"Data to emit: {type(data).__name__} = {data}")
        self.update_live_signal.emit(data)

    def emit_data_incorrectly(self):
        """Test incorrect data emission (passing method instead of result)."""
        logger.info("Testing INCORRECT emission: self.update_live_signal.emit(self.sensorgram_data)")
        logger.info(f"Method to emit: {type(self.sensorgram_data).__name__}")
        self.update_live_signal.emit(self.sensorgram_data)  # BUG: passing method, not result

    def emit_signal_emitter(self):
        """Test passing a SignalEmitter object."""
        logger.info("Testing SignalEmitter object emission")
        fake_emitter = MockSignalEmitter()
        logger.info(f"SignalEmitter to emit: {type(fake_emitter).__name__}")
        self.update_live_signal.emit(fake_emitter)  # BUG: passing SignalEmitter object

def create_dummy_emitter(signal_name: str):
    """Create a dummy signal emitter like the state machine does."""
    def emit_to_ui(*args: Any) -> None:
        logger.info(f"🔔 emit_to_ui called for {signal_name} with {len(args)} args")
        if len(args) > 0:
            data = args[0]
            logger.info(f"🔍 First arg: type={type(data).__name__}, hasattr_emit={hasattr(data, 'emit')}")

            # New filtering logic: more specific about what to block
            data_type_name = type(data).__name__
            if hasattr(data, 'emit') and (
                'Signal' in data_type_name or
                'Emitter' in data_type_name or
                callable(getattr(data, 'emit', None))
            ):
                logger.error(f"🚨 BLOCKED signal-like object for {signal_name}: {type(data)}")
                return

            logger.info(f"✅ ALLOWED data for {signal_name}: {type(data).__name__}")
            # This is where UI update would happen
            logger.info(f"📊 Data content: {data}")

    # Create an object that has an emit method
    class DummyEmitter:
        def emit(self, *args):
            emit_to_ui(*args)

    return DummyEmitter()

def main():
    logger.info("=== Testing Signal Routing ===")

    # Test 1: Direct mock signal emitter
    logger.info("\n1. Testing with MockSignalEmitter:")
    mock_emitter = MockSignalEmitter()
    data_acq = MockDataAcquisition(mock_emitter)
    data_acq.emit_data_correctly()

    # Test 2: Dummy emitter (like state machine creates)
    logger.info("\n2. Testing with dummy emitter (correct call):")
    dummy_emitter = create_dummy_emitter('update_live_signal')
    data_acq2 = MockDataAcquisition(dummy_emitter)
    data_acq2.emit_data_correctly()

    # Test 3: Dummy emitter with incorrect call
    logger.info("\n3. Testing with dummy emitter (incorrect call - method instead of result):")
    data_acq3 = MockDataAcquisition(dummy_emitter)
    data_acq3.emit_data_incorrectly()

    # Test 4: Dummy emitter with SignalEmitter object
    logger.info("\n4. Testing with dummy emitter (SignalEmitter object):")
    data_acq4 = MockDataAcquisition(dummy_emitter)
    data_acq4.emit_signal_emitter()

    logger.info("\n=== Test completed ===")

if __name__ == "__main__":
    main()