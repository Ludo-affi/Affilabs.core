"""Direct valve test - check if valve commands are working."""
import sys
import time
from affilabs.utils.logger import logger

# Connect to controller
from affilabs.utils.controller import PicoP4PRO

logger.info("=" * 80)
logger.info("DIRECT VALVE TEST - P4PRO")
logger.info("=" * 80)

ctrl = PicoP4PRO()
if not ctrl.open():
    logger.error("Failed to open controller!")
    sys.exit(1)

logger.info(f"Controller connected: {type(ctrl).__name__}")
logger.info(f"Firmware: {ctrl.firmware_id if hasattr(ctrl, 'firmware_id') else 'Unknown'}")
logger.info("")

# Test 1: Individual 6-port valve command
logger.info("TEST 1: Individual 6-port valve (v611)")
logger.info("Sending: v611 (valve 1 to INJECT)")
ctrl._ser.write(b"v611\n")
time.sleep(0.1)
response = ctrl._ser.read(100)
logger.info(f"Response: {response!r}")
logger.info("")

# Test 2: Broadcast 6-port valve command
logger.info("TEST 2: Broadcast 6-port valve command (v6B1)")
logger.info("Sending: v6B1 (both valves to INJECT)")
ctrl._ser.write(b"v6B1\n")
time.sleep(0.1)
response = ctrl._ser.read(100)
logger.info(f"Response: {response!r}")
logger.info("")

# Test 3: Set back to LOAD (OFF)
logger.info("TEST 3: Set both valves to LOAD (v6B0)")
logger.info("Sending: v6B0 (both valves to LOAD/OFF)")
ctrl._ser.write(b"v6B0\n")
time.sleep(0.1)
response = ctrl._ser.read(100)
logger.info(f"Response: {response!r}")
logger.info("")

# Test 4: Test 3-way valve broadcast
logger.info("TEST 4: Broadcast 3-way valve command (v3B1)")
logger.info("Sending: v3B1 (both 3-way valves to LOAD)")
ctrl._ser.write(b"v3B1\n")
time.sleep(0.1)
response = ctrl._ser.read(100)
logger.info(f"Response: {response!r}")
logger.info("")

# Test 5: Set 3-way back to WASTE
logger.info("TEST 5: Set both 3-way valves to WASTE (v3B0)")
logger.info("Sending: v3B0 (both 3-way to WASTE)")
ctrl._ser.write(b"v3B0\n")
time.sleep(0.1)
response = ctrl._ser.read(100)
logger.info(f"Response: {response!r}")
logger.info("")

logger.info("=" * 80)
logger.info("VALVE TEST COMPLETE")
logger.info("=" * 80)
logger.info("If all responses are b'1', valves are working!")
logger.info("If responses are b'' or something else, there's a firmware issue.")

ctrl.close()
