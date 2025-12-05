"""
Test LED Normalization with Existing HAL

Demonstrates how LED normalization uses existing src.hardware interfaces.
NO NEW ADAPTERS NEEDED!
"""

import logging
import sys

# Import existing HAL components
from src.hardware.device_interface import IController, ISpectrometer
from src.hardware.controller_adapter import wrap_existing_controller
from src.hardware.spectrometer_adapter import wrap_existing_spectrometer

# Import LED normalizer
from src.utils.led_normalization import (
    LEDNormalizer,
    PeakIntensityCalculator,
    MeanIntensityCalculator,
    IntegratedIntensityCalculator
)

# Import legacy hardware (for wrapping)
from src.utils.controller import PicoP4SPR
from src.utils.usb4000_wrapper import USB4000Wrapper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_led_normalization_with_hal():
    """Test LED normalization using existing HAL infrastructure."""
    
    logger.info("="*60)
    logger.info("LED NORMALIZATION - USING EXISTING HAL")
    logger.info("="*60)
    
    # ========================================================================
    # STEP 1: Create hardware instances (your legacy hardware)
    # ========================================================================
    logger.info("\n[1] Creating legacy hardware instances...")
    
    # Your existing hardware initialization
    picop4spr = PicoP4SPR(port='COM5')
    usb4000 = USB4000Wrapper()
    
    # ========================================================================
    # STEP 2: Wrap with HAL adapters (existing functions!)
    # ========================================================================
    logger.info("\n[2] Wrapping with existing HAL adapters...")
    
    # Use existing HAL wrapper functions
    controller: IController = wrap_existing_controller(picop4spr)
    spectrometer: ISpectrometer = wrap_existing_spectrometer(usb4000)
    
    logger.info(f"  Controller: {controller.get_info().model}")
    logger.info(f"  Spectrometer: {spectrometer.get_info().model}")
    
    # ========================================================================
    # STEP 3: Connect devices
    # ========================================================================
    logger.info("\n[3] Connecting devices...")
    
    if not controller.connect():
        logger.error("Failed to connect controller")
        return
    
    if not spectrometer.connect():
        logger.error("Failed to connect spectrometer")
        controller.disconnect()
        return
    
    logger.info("  ✓ All devices connected")
    
    try:
        # ====================================================================
        # STEP 4: Create LED normalizer (uses HAL interfaces directly)
        # ====================================================================
        logger.info("\n[4] Creating LED normalizer...")
        
        # Choose intensity calculation method
        intensity_calc = PeakIntensityCalculator()
        # intensity_calc = MeanIntensityCalculator(wavelength_min=500, wavelength_max=600)
        # intensity_calc = IntegratedIntensityCalculator(wavelength_min=500, wavelength_max=600)
        
        normalizer = LEDNormalizer(
            controller=controller,        # IController from HAL
            spectrometer=spectrometer,    # ISpectrometer from HAL
            intensity_calculator=intensity_calc
        )
        
        logger.info("  ✓ LED normalizer created (using existing HAL)")
        
        # ====================================================================
        # STEP 5: Rank LEDs
        # ====================================================================
        logger.info("\n[5] Ranking LEDs (brightest to dimmest)...")
        
        ranked, recommended_target = normalizer.rank_leds(
            test_intensity=255,
            integration_time=10,
            settling_time=0.2
        )
        
        logger.info("\n  Ranking Results:")
        for i, (led, intensity) in enumerate(ranked.items(), 1):
            logger.info(f"    {i}. LED {led}: {intensity:.0f} counts")
        logger.info(f"\n  Recommended target: {recommended_target:.0f} counts")
        
        # ====================================================================
        # STEP 6: Normalize by Intensity
        # ====================================================================
        logger.info("\n[6] Normalizing by INTENSITY (fixed integration time)...")
        
        results_intensity = normalizer.normalize(
            mode='intensity',
            target_value=30000,
            tolerance=500,
            max_iterations=10,
            settling_time=0.2
        )
        
        logger.info("\n  Intensity Normalization Results:")
        for led, result in results_intensity.items():
            logger.info(f"    LED {led}:")
            logger.info(f"      Intensity: {result['value']}")
            logger.info(f"      Integration time: {result['integration_time']}ms")
            logger.info(f"      Achieved: {result['achieved_count']:.0f} counts")
            logger.info(f"      Error: {result['error']:.0f} ({result['error_percent']:.1f}%)")
        
        # Save results
        normalizer.save_results(results_intensity, 'led_normalization_intensity.json')
        
        # ====================================================================
        # STEP 7: Normalize by Time
        # ====================================================================
        logger.info("\n[7] Normalizing by TIME (fixed intensity)...")
        
        results_time = normalizer.normalize(
            mode='time',
            target_value=30000,
            tolerance=500,
            max_iterations=10,
            settling_time=0.2
        )
        
        logger.info("\n  Time Normalization Results:")
        for led, result in results_time.items():
            logger.info(f"    LED {led}:")
            logger.info(f"      Intensity: {result['intensity']}")
            logger.info(f"      Integration time: {result['value']}ms")
            logger.info(f"      Achieved: {result['achieved_count']:.0f} counts")
            logger.info(f"      Error: {result['error']:.0f} ({result['error_percent']:.1f}%)")
        
        # Save results
        normalizer.save_results(results_time, 'led_normalization_time.json')
        
        # ====================================================================
        # STEP 8: Apply saved normalization
        # ====================================================================
        logger.info("\n[8] Applying saved normalization for LED A...")
        
        normalizer.apply_normalization(results_intensity, 'A')
        controller.turn_on_channel('A')
        
        logger.info("  ✓ LED A configured with normalized parameters")
        logger.info("  (LED is now on with normalized settings)")
        
    finally:
        # ====================================================================
        # CLEANUP
        # ====================================================================
        logger.info("\n[CLEANUP] Disconnecting devices...")
        controller.disconnect()
        spectrometer.disconnect()
        logger.info("  ✓ All devices disconnected")


def test_with_device_manager():
    """
    Alternative: Use DeviceManager for multi-device coordination.
    
    This shows how to use the existing DeviceManager infrastructure
    for lifecycle management and health monitoring.
    """
    from src.hardware.device_manager import DeviceManager
    
    logger.info("="*60)
    logger.info("LED NORMALIZATION - WITH DEVICE MANAGER")
    logger.info("="*60)
    
    # Create device manager
    manager = DeviceManager()
    
    # Create and register devices
    picop4spr = PicoP4SPR(port='COM5')
    usb4000 = USB4000Wrapper()
    
    controller = wrap_existing_controller(picop4spr)
    spectrometer = wrap_existing_spectrometer(usb4000)
    
    manager.register_controller('main_controller', controller)
    manager.register_spectrometer('main_spectrometer', spectrometer)
    
    # Connect all devices
    if not manager.connect_all():
        logger.error("Failed to connect all devices")
        return
    
    try:
        # Get devices from manager
        ctrl = manager.get_controller('main_controller')
        spec = manager.get_spectrometer('main_spectrometer')
        
        # Create normalizer
        normalizer = LEDNormalizer(ctrl, spec)
        
        # Run normalization
        results = normalizer.normalize(mode='intensity', target_value=30000)
        
        logger.info(f"\nNormalization complete: {len(results)} LEDs normalized")
        
        # Check system health
        health = manager.get_health()
        logger.info(f"System health: {health.state}")
        
    finally:
        manager.disconnect_all()


def test_with_mock_devices():
    """
    Test with mock devices (no hardware required).
    
    Uses existing mock_devices.py from your HAL.
    """
    from src.hardware.mock_devices import MockController, MockSpectrometer
    
    logger.info("="*60)
    logger.info("LED NORMALIZATION - MOCK DEVICES (NO HARDWARE)")
    logger.info("="*60)
    
    # Create mock devices (existing HAL mocks)
    controller = MockController(device_id='mock_controller')
    spectrometer = MockSpectrometer(device_id='mock_spectrometer')
    
    # Connect
    controller.connect()
    spectrometer.connect()
    
    try:
        # Create normalizer (same code as real hardware!)
        normalizer = LEDNormalizer(controller, spectrometer)
        
        # Rank LEDs
        ranked, target = normalizer.rank_leds()
        logger.info(f"\nRanking: {list(ranked.keys())}")
        logger.info(f"Target: {target:.0f} counts")
        
        # Normalize
        results = normalizer.normalize(mode='intensity', target_value=30000)
        
        logger.info("\nNormalization Results:")
        for led, result in results.items():
            logger.info(f"  LED {led}: intensity={result['value']}, "
                       f"achieved={result['achieved_count']:.0f}")
        
        logger.info("\n✓ Mock test successful (no hardware needed)")
        
    finally:
        controller.disconnect()
        spectrometer.disconnect()


if __name__ == '__main__':
    print("\n" + "="*60)
    print("LED NORMALIZATION TEST")
    print("Uses EXISTING HAL - No new adapters needed!")
    print("="*60)
    print("\nSelect test mode:")
    print("  1. Real hardware (requires PicoP4SPR + USB4000)")
    print("  2. DeviceManager (coordinated multi-device)")
    print("  3. Mock devices (no hardware required)")
    print("="*60)
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == '1':
        test_led_normalization_with_hal()
    elif choice == '2':
        test_with_device_manager()
    elif choice == '3':
        test_with_mock_devices()
    else:
        print("Invalid choice")
        sys.exit(1)
