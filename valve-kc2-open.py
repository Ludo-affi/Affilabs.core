#!/usr/bin/env python3
"""Control 6-port valves for KC1 and KC2"""

import sys
import os
import argparse

# Add affilabs to path
parent_dir = os.path.dirname(os.path.abspath(__file__))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from affilabs.core.hardware_manager import HardwareManager
from affilabs.utils.logger import logger

def main():
    parser = argparse.ArgumentParser(description="Control 6-port valves for KC1 and KC2")
    parser.add_argument("--pump", type=int, choices=[1, 2], default=2,
                        help="Pump number: 1 (KC1) or 2 (KC2) [default: 2]")
    parser.add_argument("--state", type=str, choices=['open', 'close', '1', '0'], default='open',
                        help="Valve state: open/1 (INJECT) or close/0 (LOAD) [default: open]")
    args = parser.parse_args()

    # Convert state to numeric
    if args.state in ['open', '1']:
        state = 1
        state_name = "INJECT"
    else:
        state = 0
        state_name = "LOAD"

    pump_name = f"KC{args.pump}"
    logger.info(f"Setting {pump_name}'s 6-port valve to {state_name}...")

    # Initialize hardware
    hm = HardwareManager()

    # Connect to controller
    logger.info("Connecting to controller...")
    hm._connect_controller()

    if not hm.ctrl:
        logger.error("❌ Controller not found")
        return False

    logger.info(f"✅ Controller connected: {hm.ctrl.get_device_type()}")

    # Control 6-port valve
    success = hm._ctrl_raw.knx_six(state, args.pump)

    if success:
        logger.info(f"✅ {pump_name}'s 6-port valve set to {state_name}")
    else:
        logger.error(f"❌ Failed to set {pump_name}'s 6-port valve")

    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
