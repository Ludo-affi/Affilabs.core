"""AffiPump - Tecan Cavro Centris dual syringe pump controller.

This package provides control for the AffiPump system used in Affilabs SPR instruments.
"""

import serial.tools.list_ports
from .affipump_controller import AffipumpController


class PumpController:
    """Wrapper for Aff ipumpController with factory method for auto-detection."""
    
    @classmethod
    def from_first_available(cls):
        """Find and connect to first available FTDI pump controller.
        
        Tries FTDI auto-detection first, then falls back to common COM ports.
        
        Returns:
            AffipumpController instance if found, None otherwise
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Try FTDI auto-detection first
        logger.info("   → Trying FTDI auto-detection...")
        ports = serial.tools.list_ports.comports()
        for port in ports:
            # FTDI VID/PID: 0403:6001 or similar
            if port.vid == 0x0403:  # FTDI vendor ID
                try:
                    logger.info(f"   → Trying FTDI device on {port.device}...")
                    controller = AffipumpController(port=port.device)
                    controller.open()
                    logger.info(f"   ✅ Connected via FTDI on {port.device}")
                    return controller
                except Exception as e:
                    logger.debug(f"   → Failed on {port.device}: {e}")
                    continue
        
        # Fallback: Try common pump COM ports directly
        logger.info("   → FTDI auto-detection failed, trying direct COM ports...")
        for port_name in ['COM8', 'COM7', 'COM6', 'COM5']:
            try:
                logger.info(f"   → Trying {port_name}...")
                controller = AffipumpController(port=port_name)
                controller.open()
                # Test if pump responds with a simple query
                try:
                    controller.send_command("/1?")  # Query pump 1
                except Exception:
                    pass  # Pump might not respond to ? command, but connection is valid
                logger.info(f"   ✅ Connected via direct port {port_name}")
                return controller
            except Exception as e:
                logger.debug(f"   → {port_name} failed: {e}")
                try:
                    controller.close()
                except Exception:
                    pass
                continue
        
        logger.info("   ❌ No pump found on any port")
        return None


class CavroPumpManager:
    """Manager for dual Cavro pump setup with HAL-compatible interface."""
    
    def __init__(self, controller):
        """Initialize with a pump controller instance.
        
        Args:
            controller: AffipumpController or PumpController instance
        """
        self.pump = controller
        self._initialized = False
    
    def initialize_pumps(self):
        """Initialize both pumps.
        
        Returns:
            True if successful
        """
        try:
            # Initialize pump 1
            self.pump.send_command("/1ZR")
            # Initialize pump 2
            self.pump.send_command("/2ZR")
            self._initialized = True
            return True
        except Exception:
            return False
    
    def is_available(self):
        """Check if pump is available.
        
        Returns:
            True if pump is connected and initialized
        """
        return self.pump is not None and self._initialized
    
    def aspirate(self, pump_address, volume_ul, rate_ul_min):
        """Aspirate fluid.
        
        Args:
            pump_address: Pump number (1 or 2)
            volume_ul: Volume in microliters
            rate_ul_min: Flow rate in µL/min
            
        Returns:
            True if command sent successfully
        """
        try:
            rate_ul_s = rate_ul_min / 60.0
            self.pump.aspirate(pump_address, volume_ul, rate_ul_s)
            return True
        except Exception:
            return False
    
    def dispense(self, pump_address, volume_ul, rate_ul_min):
        """Dispense fluid.
        
        Args:
            pump_address: Pump number (1 or 2)
            volume_ul: Volume in microliters
            rate_ul_min: Flow rate in µL/min
            
        Returns:
            True if command sent successfully
        """
        try:
            rate_ul_s = rate_ul_min / 60.0
            self.pump.dispense(pump_address, volume_ul, rate_ul_s)
            return True
        except Exception:
            return False
    
    def set_valve_position(self, pump_address, port):
        """Set valve position.
        
        Args:
            pump_address: Pump number (1 or 2)
            port: Valve port number
        """
        self.pump.send_command(f"/{pump_address}O{port}R")
    
    def get_syringe_position(self, pump_address):
        """Get current syringe position.
        
        Args:
            pump_address: Pump number (1 or 2)
            
        Returns:
            Position in steps or None
        """
        response = self.pump.send_command(f"/{pump_address}?")
        parsed = self.pump.parse_response(response)
        if parsed and parsed['data']:
            try:
                return int(parsed['data'])
            except ValueError:
                return None
        return None
    
    def wait_until_idle(self, pump_address, timeout_s=60.0):
        """Wait for pump to finish current operation.
        
        Args:
            pump_address: Pump number (1 or 2)
            timeout_s: Maximum wait time in seconds
            
        Returns:
            True if pump became idle, False if timeout
        """
        import time
        start_time = time.time()
        while (time.time() - start_time) < timeout_s:
            status = self.pump.get_status(pump_address)
            if status and not status.get('busy', True):
                return True
            time.sleep(0.1)
        return False
    
    def close(self):
        """Close connection to pump."""
        if self.pump:
            self.pump.close()


__all__ = ["AffipumpController", "PumpController", "CavroPumpManager"]
