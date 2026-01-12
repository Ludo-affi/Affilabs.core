"""Test script for all three injection methods.

This script demonstrates how to use each of the three injection methods:
1. Simple Injection (recommended default)
2. Partial Loop Injection (advanced)
3. Complex Injection (original with KC2 priming)

Usage:
    python test_injection_methods.py [method]
    
    method: "simple", "partial_loop", or "default" (default: "simple")

Examples:
    python test_injection_methods.py
    python test_injection_methods.py simple
    python test_injection_methods.py partial_loop
    python test_injection_methods.py default
"""

import asyncio
import sys

from affilabs.utils.logger import logger


async def test_injection_method(method: str = "simple"):
    """Test the specified injection method.
    
    Args:
        method: Injection method ("simple", "partial_loop", or "default")
    """
    logger.info("\n" + "=" * 80)
    logger.info(f" TESTING INJECTION METHOD: {method.upper()}")
    logger.info("=" * 80 + "\n")
    
    # Import hardware manager
    logger.info("1. Initializing hardware manager...")
    try:
        from affilabs.core.hardware_manager import HardwareManager
        hw_manager = HardwareManager()
        logger.info("✓ Hardware manager created")
    except Exception as e:
        logger.error(f"❌ Failed to create hardware manager: {e}")
        return False

    # Create pump manager
    logger.info("\n2. Creating pump manager...")
    try:
        from affilabs.managers.pump_manager import PumpManager
        pump_mgr = PumpManager(hw_manager)
        logger.info("✓ Pump manager created")
    except Exception as e:
        logger.error(f"❌ Failed to create pump manager: {e}")
        return False

    # Test parameters
    logger.info("\n3. Test parameters:")
    assay_flow_rate = 15.0  # µL/min (typical from sidebar)
    aspiration_flow_rate = 24000.0  # µL/min (default fast)
    loop_volume = 100.0  # µL
    valve_open_delay = 30.0  # seconds (for simple and default methods)
    pulse_rate = 900.0  # µL/min (for default method only)

    logger.info(f"   Assay flow rate: {assay_flow_rate} µL/min")
    logger.info(f"   Aspiration flow rate: {aspiration_flow_rate} µL/min")
    logger.info(f"   Loop volume: {loop_volume} µL")
    logger.info(f"   Valve open delay: {valve_open_delay}s")
    if method == "default":
        logger.info(f"   Pulse rate (KC2): {pulse_rate} µL/min")

    # Calculate expected contact time
    contact_time = (loop_volume / assay_flow_rate) * 60.0
    logger.info(f"   Expected contact time: {contact_time:.2f}s ({contact_time/60:.2f} min)")

    # Method-specific information
    logger.info("\n4. Method description:")
    if method == "simple":
        logger.info("   SIMPLE INJECTION (Recommended Default)")
        logger.info("   - Aspirate → dispense → wait 30s → open valves → contact time → close")
        logger.info("   - Minimal valve switching, fastest execution")
        logger.info("   - Best for routine experiments")
    elif method == "partial_loop":
        logger.info("   PARTIAL LOOP INJECTION (Advanced)")
        logger.info("   - Aspirate 900µL → flip valves → aspirate 100µL from output")
        logger.info("   - Push 50µL → wait → push 40µL → contact time")
        logger.info("   - Fills loop from pump output, not sample source")
        logger.info("   - Best for small sample volumes")
    elif method == "default":
        logger.info("   COMPLEX INJECTION (Original)")
        logger.info("   - KC1 dispense + KC2 prime/backflush sequence")
        logger.info("   - Both channels dispense → wait 30s → open valves")
        logger.info("   - KC2 pulsing during injection")
        logger.info("   - Most complex, longest execution time")
    
    # Confirm before starting
    logger.info("\n" + "=" * 80)
    logger.info(" READY TO START INJECTION")
    logger.info("=" * 80)
    logger.info(f"\n⚠️  This will run a REAL injection using method: {method}")
    logger.info("   - Pumps will aspirate and dispense")
    logger.info("   - Valves will switch")
    logger.info(f"   - Estimated duration: ~{contact_time/60 + 3:.1f} minutes")
    
    response = input("\nProceed? (yes/no): ").lower().strip()
    if response not in ["yes", "y"]:
        logger.info("❌ Injection cancelled by user")
        return False

    # Run injection
    logger.info("\n5. Starting injection sequence...")
    logger.info("=" * 80 + "\n")
    
    try:
        success = await pump_mgr.inject_with_valve_timing(
            assay_flow_rate=assay_flow_rate,
            aspiration_flow_rate=aspiration_flow_rate,
            loop_volume_ul=loop_volume,
            valve_open_delay_s=valve_open_delay,
            pulse_rate=pulse_rate,
            method=method,
        )

        logger.info("\n" + "=" * 80)
        if success:
            logger.info("✅ INJECTION COMPLETED SUCCESSFULLY!")
            logger.info("=" * 80 + "\n")
            return True
        else:
            logger.error("❌ INJECTION FAILED!")
            logger.info("=" * 80 + "\n")
            return False

    except Exception as e:
        logger.exception(f"❌ Injection error: {e}")
        logger.info("=" * 80 + "\n")
        return False


async def main():
    """Main entry point."""
    # Parse command line arguments
    method = "simple"  # Default
    if len(sys.argv) > 1:
        method = sys.argv[1].lower()
    
    # Validate method
    valid_methods = ["simple", "partial_loop", "default"]
    if method not in valid_methods:
        logger.error(f"❌ Invalid method: {method}")
        logger.error(f"   Valid methods: {', '.join(valid_methods)}")
        sys.exit(1)
    
    # Run test
    success = await test_injection_method(method)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    # Display help if requested
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help", "help"]:
        print(__doc__)
        sys.exit(0)
    
    # Run the async test
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Interrupted by user (Ctrl+C)")
        sys.exit(1)
