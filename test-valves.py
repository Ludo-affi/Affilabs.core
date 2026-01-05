#!/usr/bin/env python3
"""
Test 6-port and 3-way valve control
"""
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s :: %(levelname)s :: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def test_valves():
    """Test 6-port and 3-way valve operation"""
    from affilabs.core.hardware_manager import HardwareManager
    
    logger.info("=== Valve Test Started ===")
    
    # Connect to controller
    hm = HardwareManager()
    logger.info("Connecting to controller...")
    
    try:
        hm._connect_controller()
        
        if not hm.ctrl:
            logger.error("❌ No controller found")
            logger.info("Check:")
            logger.info("  - Controller powered on")
            logger.info("  - USB cable connected")
            logger.info("  - COM port available")
            return False
        
        logger.info(f"✅ Controller connected: {hm.ctrl.get_device_type()}")
        ctrl = hm._ctrl_raw  # Get raw controller for knx methods
        
        # Test 6-port valves (load valves)
        logger.info("\n=== Testing 6-Port Valves (Load Valves) ===")
        
        logger.info("\n1. Opening KC1 6-port valve (ch=1, state=1)...")
        ctrl.knx_six(state=1, ch=1)
        time.sleep(2)
        logger.info("   ✓ Command sent")
        
        logger.info("\n2. Closing KC1 6-port valve (ch=1, state=0)...")
        ctrl.knx_six(state=0, ch=1)
        time.sleep(2)
        logger.info("   ✓ Command sent")
        
        logger.info("\n3. Opening KC2 6-port valve (ch=2, state=1)...")
        ctrl.knx_six(state=1, ch=2)
        time.sleep(2)
        logger.info("   ✓ Command sent")
        
        logger.info("\n4. Closing KC2 6-port valve (ch=2, state=0)...")
        ctrl.knx_six(state=0, ch=2)
        time.sleep(2)
        logger.info("   ✓ Command sent")
        
        # Test 3-way valves (channel valves)
        logger.info("\n=== Testing 3-Way Valves (Channel Valves) ===")
        
        logger.info("\n5. Opening KC1 3-way valve (ch=1, state=1)...")
        ctrl.knx_three(state=1, ch=1)
        time.sleep(2)
        logger.info("   ✓ Command sent")
        
        logger.info("\n6. Closing KC1 3-way valve (ch=1, state=0)...")
        ctrl.knx_three(state=0, ch=1)
        time.sleep(2)
        logger.info("   ✓ Command sent")
        
        logger.info("\n7. Opening KC2 3-way valve (ch=2, state=1)...")
        ctrl.knx_three(state=1, ch=2)
        time.sleep(2)
        logger.info("   ✓ Command sent")
        
        logger.info("\n8. Closing KC2 3-way valve (ch=2, state=0)...")
        ctrl.knx_three(state=0, ch=2)
        time.sleep(2)
        logger.info("   ✓ Command sent")
        
        logger.info("\n=== All Valve Commands Sent Successfully ===")
        logger.info("\nListen for valve clicking sounds to verify operation.")
        logger.info("If you hear clicks, valves are responding to commands.")
        
        return True
        
    except Exception as e:
        logger.exception(f"Valve test failed: {e}")
        return False


if __name__ == "__main__":
    test_valves()
