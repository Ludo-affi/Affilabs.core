"""
Hardware Detection Utilities

Automatically detects and identifies connected hardware:
- Spectrometer (Ocean Optics Flame-T)
- Controller (Raspberry Pi Pico P4SPR)
- LED PCB model (from user input or configuration)

Generates initial device configuration if none exists.

Author: AI Assistant
Date: October 11, 2025
Version: 1.0
"""

from __future__ import annotations

import serial.tools.list_ports
from typing import Optional, Dict, List, Tuple
from pathlib import Path
import time

from utils.logger import logger


class HardwareDetector:
    """
    Detect and identify connected SPR hardware.

    Detects:
    - Spectrometer (via serial port VID:PID)
    - Controller (Raspberry Pi Pico)
    - Generates device configuration
    """

    # Known hardware identifiers
    SPECTROMETER_VID_PID = [
        ('2457', '101E'),  # Ocean Optics USB4000 (direct USB)
        ('2457', '1022'),  # Ocean Optics Flame-S (direct USB)
        ('10C4', 'EA60'),  # CP210x USB-to-Serial (used by USB4000/Flame-T)
    ]

    CONTROLLER_VID_PID = [
        ('2E8A', '000A'),  # Raspberry Pi Pico
    ]

    def __init__(self):
        """Initialize hardware detector."""
        self.detected_hardware = {
            'spectrometer': None,
            'controller': None,
            'led_pcb': None,  # Must be set by user
        }

    def scan_ports(self) -> List[Dict[str, str]]:
        """
        Scan all available serial ports.

        Returns:
            List of port information dictionaries
        """
        ports = []
        for port in serial.tools.list_ports.comports():
            port_info = {
                'device': port.device,
                'name': port.name,
                'description': port.description,
                'hwid': port.hwid,
                'vid': f"{port.vid:04X}" if port.vid else None,
                'pid': f"{port.pid:04X}" if port.pid else None,
                'serial_number': port.serial_number,
                'manufacturer': port.manufacturer,
                'product': port.product,
            }
            ports.append(port_info)

        return ports

    def detect_spectrometer(self) -> Optional[Dict[str, str]]:
        """
        Detect Ocean Optics spectrometer using SeaBreeze.

        Returns:
            Spectrometer information if found, None otherwise
        """
        logger.info("Scanning for spectrometer...")

        # Try SeaBreeze detection first (Ocean Optics native USB)
        try:
            import seabreeze
            # Use cseabreeze (C backend) - more reliable than pyseabreeze
            seabreeze.use('cseabreeze')
            from seabreeze.spectrometers import list_devices, Spectrometer

            devices = list_devices()

            if devices:
                # Get first device
                device = devices[0]

                # Try to open to get details
                try:
                    spec = Spectrometer(device)

                    spec_info = {
                        'device': 'SeaBreeze',
                        'name': spec.model,
                        'description': f"Ocean Optics {spec.model}",
                        'hwid': 'SeaBreeze',
                        'vid': None,  # Not exposed by SeaBreeze
                        'pid': None,
                        'serial_number': spec.serial_number,
                        'manufacturer': 'Ocean Optics',
                        'product': spec.model,
                        'connection_type': 'USB (SeaBreeze)',
                    }

                    spec.close()

                    logger.info(f"  ✅ Found spectrometer via SeaBreeze")
                    logger.info(f"     Model: {spec_info['product']}")
                    logger.info(f"     Serial: {spec_info['serial_number']}")

                    self.detected_hardware['spectrometer'] = spec_info
                    return spec_info

                except Exception as e:
                    logger.debug(f"  Could not open SeaBreeze device: {e}")

        except ImportError:
            logger.debug("  SeaBreeze not available")
        except Exception as e:
            logger.debug(f"  SeaBreeze detection failed: {e}")

        # Fallback: Try serial port detection (CP210x USB-to-Serial)
        ports = self.scan_ports()

        for port in ports:
            vid = port['vid']
            pid = port['pid']

            # Check if this is a known spectrometer via serial
            for spec_vid, spec_pid in self.SPECTROMETER_VID_PID:
                if vid == spec_vid and pid == spec_pid:
                    logger.info(f"  ✅ Found spectrometer on {port['device']}")
                    logger.info(f"     VID:PID = {vid}:{pid}")
                    logger.info(f"     Serial: {port['serial_number']}")
                    logger.info(f"     Product: {port['product']}")

                    self.detected_hardware['spectrometer'] = port
                    return port

        logger.warning("  ❌ No spectrometer detected")
        return None

    def detect_controller(self) -> Optional[Dict[str, str]]:
        """
        Detect Raspberry Pi Pico controller.

        Returns:
            Port information if found, None otherwise
        """
        logger.info("Scanning for controller...")

        ports = self.scan_ports()

        for port in ports:
            vid = port['vid']
            pid = port['pid']

            # Check if this is a Pico
            for ctrl_vid, ctrl_pid in self.CONTROLLER_VID_PID:
                if vid == ctrl_vid and pid == ctrl_pid:
                    logger.info(f"  ✅ Found controller on {port['device']}")
                    logger.info(f"     VID:PID = {vid}:{pid}")
                    logger.info(f"     Product: {port['product']}")

                    self.detected_hardware['controller'] = port
                    return port

        logger.warning("  ❌ No controller detected")
        return None

    def detect_all_hardware(self) -> Dict[str, Optional[Dict]]:
        """
        Detect all connected hardware.

        Returns:
            Dictionary with detected hardware info
        """
        logger.info("\n" + "=" * 60)
        logger.info("HARDWARE DETECTION")
        logger.info("=" * 60)

        # Scan for devices
        self.detect_spectrometer()
        self.detect_controller()

        # Summary
        logger.info("\n📊 Detection Summary:")
        logger.info(f"  Spectrometer: {'✅ Detected' if self.detected_hardware['spectrometer'] else '❌ Not found'}")
        logger.info(f"  Controller:   {'✅ Detected' if self.detected_hardware['controller'] else '❌ Not found'}")
        logger.info(f"  LED PCB:      ⚠️  User input required")

        logger.info("=" * 60)

        return self.detected_hardware

    def query_spectrometer_info(self, port: str) -> Optional[Dict[str, str]]:
        """
        Query spectrometer for detailed information.

        Args:
            port: Serial port device path

        Returns:
            Spectrometer info dictionary
        """
        try:
            import seabreeze
            seabreeze.use('cseabreeze')  # FIX: Use C backend for performance (was pyseabreeze)
            from seabreeze.spectrometers import Spectrometer

            # Try to open spectrometer
            spec = Spectrometer.from_serial_number()

            info = {
                'model': spec.model,
                'serial_number': spec.serial_number,
                'wavelengths': len(spec.wavelengths()),
                'integration_time_min': spec.integration_time_micros_limits[0],
                'integration_time_max': spec.integration_time_micros_limits[1],
            }

            spec.close()
            return info

        except Exception as e:
            logger.debug(f"Could not query spectrometer details: {e}")
            return None

    def generate_device_config(
        self,
        led_pcb_model: str = 'luminus_cool_white',
        fiber_diameter_um: int = 200
    ) -> Dict:
        """
        Generate device configuration from detected hardware.

        Args:
            led_pcb_model: LED PCB model ('luminus_cool_white' or 'osram_warm_white')
            fiber_diameter_um: Optical fiber diameter (100 or 200)

        Returns:
            Configuration dictionary
        """
        from datetime import datetime

        config = {
            'device_info': {
                'config_version': '1.0',
                'created_date': datetime.now().isoformat(),
                'last_modified': datetime.now().isoformat(),
                'device_id': None,
                'auto_detected': True,
            },
            'hardware': {
                'led_pcb_model': led_pcb_model,
                'led_pcb_serial': None,
                'spectrometer_model': 'Flame-T',
                'spectrometer_serial': None,
                'controller_model': 'Raspberry Pi Pico P4SPR',
                'controller_serial': None,
                'optical_fiber_diameter_um': fiber_diameter_um,
            },
            'timing_parameters': {
                'led_a_delay_ms': 0,
                'led_b_delay_ms': 0,
                'led_c_delay_ms': 0,
                'led_d_delay_ms': 0,
                'min_integration_time_ms': 50,
                'led_rise_fall_time_ms': 5,
            },
            'frequency_limits': {
                '4_led_max_hz': 5.0,
                '4_led_recommended_hz': 2.0,
                '2_led_max_hz': 10.0,
                '2_led_recommended_hz': 5.0,
            },
            'calibration': {
                'dark_calibration_date': None,
                's_mode_calibration_date': None,
                'p_mode_calibration_date': None,
                'factory_calibrated': False,
                'user_calibrated': False,
            },
            'maintenance': {
                'last_maintenance_date': None,
                'total_measurement_cycles': 0,
                'led_on_hours': 0.0,
                'next_maintenance_due': None,
            },
        }

        # Fill in detected hardware info
        if self.detected_hardware['spectrometer']:
            spec = self.detected_hardware['spectrometer']
            config['hardware']['spectrometer_serial'] = spec['serial_number']

        if self.detected_hardware['controller']:
            ctrl = self.detected_hardware['controller']
            config['hardware']['controller_serial'] = ctrl['serial_number']

        return config

    def print_detected_hardware(self):
        """Print detailed information about detected hardware."""
        logger.info("\n" + "=" * 60)
        logger.info("DETECTED HARDWARE DETAILS")
        logger.info("=" * 60)

        # Spectrometer
        if self.detected_hardware['spectrometer']:
            spec = self.detected_hardware['spectrometer']
            logger.info("\n🔬 Spectrometer:")
            logger.info(f"  Port:         {spec['device']}")
            logger.info(f"  VID:PID:      {spec['vid']}:{spec['pid']}")
            logger.info(f"  Serial:       {spec['serial_number']}")
            logger.info(f"  Product:      {spec['product']}")
            logger.info(f"  Manufacturer: {spec['manufacturer']}")
        else:
            logger.info("\n🔬 Spectrometer: Not detected")

        # Controller
        if self.detected_hardware['controller']:
            ctrl = self.detected_hardware['controller']
            logger.info("\n🎛️  Controller:")
            logger.info(f"  Port:         {ctrl['device']}")
            logger.info(f"  VID:PID:      {ctrl['vid']}:{ctrl['pid']}")
            logger.info(f"  Product:      {ctrl['product']}")
        else:
            logger.info("\n🎛️  Controller: Not detected")

        logger.info("\n💡 LED PCB: Requires user selection")
        logger.info("  Options:")
        logger.info("    - luminus_cool_white")
        logger.info("    - osram_warm_white")

        logger.info("\n" + "=" * 60)


def auto_detect_and_configure(
    led_pcb_model: str = 'luminus_cool_white',
    fiber_diameter_um: int = 200,
    save_config: bool = True
) -> Dict:
    """
    Auto-detect hardware and create configuration.

    Args:
        led_pcb_model: LED PCB model
        fiber_diameter_um: Optical fiber diameter
        save_config: Save configuration to file

    Returns:
        Generated configuration
    """
    # Detect hardware
    detector = HardwareDetector()
    detector.detect_all_hardware()
    detector.print_detected_hardware()

    # Generate configuration
    config = detector.generate_device_config(led_pcb_model, fiber_diameter_um)

    # Save if requested
    if save_config:
        from utils.device_configuration import DeviceConfiguration
        device_config = DeviceConfiguration()

        # Update with detected values
        if config['hardware']['spectrometer_serial']:
            device_config.set_spectrometer_serial(config['hardware']['spectrometer_serial'])

        device_config.set_led_pcb_model(led_pcb_model)
        device_config.set_optical_fiber_diameter(fiber_diameter_um)
        device_config.save()

        logger.info("\n✅ Configuration saved!")

    return config


if __name__ == "__main__":
    """Test hardware detection."""
    print("\n" + "=" * 70)
    print("HARDWARE DETECTION TEST")
    print("=" * 70)

    # Run detection
    config = auto_detect_and_configure(
        led_pcb_model='luminus_cool_white',
        fiber_diameter_um=200,
        save_config=True
    )

    print("\n" + "=" * 70)
    print("DETECTION COMPLETE ✅")
    print("=" * 70)

    # List all serial ports for debugging
    print("\n📋 All Available Serial Ports:")
    print("-" * 70)
    detector = HardwareDetector()
    ports = detector.scan_ports()

    if ports:
        for i, port in enumerate(ports, 1):
            print(f"\n{i}. {port['device']}")
            print(f"   Description: {port['description']}")
            print(f"   VID:PID:     {port['vid']}:{port['pid']}")
            if port['serial_number']:
                print(f"   Serial:      {port['serial_number']}")
            if port['product']:
                print(f"   Product:     {port['product']}")
    else:
        print("No serial ports detected")

    print("\n" + "=" * 70)
