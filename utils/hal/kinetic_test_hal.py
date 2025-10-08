"""
Test implementation of KineticController HAL for development and testing.

This module provides a simulated kinetic controller that mimics the behavior
of real KNX hardware without requiring physical devices. Useful for:
- Development and testing
- UI development
- Integration testing
- Demonstration purposes
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Union

from utils.logger import logger


class KineticTestHAL:
    """
    Test implementation of Kinetic HAL.
    
    Simulates KNX kinetic controller behavior for development and testing.
    All operations are simulated but maintain realistic behavior patterns.
    """
    
    def __init__(self, device_name: str = "KNX Test Controller") -> None:
        """Initialize test kinetic HAL."""
        self.device_name = device_name
        
        # Simulated device state
        self._connected = False
        self._device_info = {
            'model': 'KNX2-Test',
            'firmware_version': 'KNX2 V1.1 (Simulated)',
            'hardware_version': '1.1',
            'serial_number': 'TEST-KNX2-001',
            'connected': False,
            'device_type': 'kinetic_controller',
            'manufacturer': 'Affinite Instruments (Test)'
        }
        
        # Simulated hardware state
        self._valve_states = {
            1: {'three_way': 0, 'six_port': 0},  # CH1
            2: {'three_way': 0, 'six_port': 0}   # CH2
        }
        self._pump_states = {
            1: {'running': False, 'rate': 0},    # CH1
            2: {'running': False, 'rate': 0}     # CH2
        }
        self._led_states = {
            1: {'on': False, 'intensity': 0},    # LED a
            2: {'on': False, 'intensity': 0},    # LED b
            3: {'on': False, 'intensity': 0},    # LED c
            4: {'on': False, 'intensity': 0}     # LED d
        }
        self._integration_time = 1000  # ms
        self._servo_mode = 's'
        self._servo_position = {'speed': 10, 'position': 100}
        
        # Simulated sensor data
        self._temperature_ch1 = 23.5  # °C
        self._temperature_ch2 = 24.1  # °C
        self._flow_rate_ch1 = 0.0     # ml/min
        self._flow_rate_ch2 = 0.0     # ml/min
        
    def connect(self, **kwargs) -> bool:
        """
        Simulate connection to kinetic controller.
        
        Returns:
            True (always successful for test implementation)
        """
        logger.info("Connecting to test KNX controller...")
        time.sleep(0.1)  # Simulate connection delay
        
        self._connected = True
        self._device_info['connected'] = True
        
        logger.info(f"Connected to test KNX controller: {self._device_info['model']}")
        return True
    
    def disconnect(self) -> bool:
        """
        Simulate disconnection from kinetic controller.
        
        Returns:
            True (always successful)
        """
        logger.info("Disconnecting from test KNX controller...")
        
        # Reset all states to safe defaults
        self._valve_states = {
            1: {'three_way': 0, 'six_port': 0},
            2: {'three_way': 0, 'six_port': 0}
        }
        self._pump_states = {
            1: {'running': False, 'rate': 0},
            2: {'running': False, 'rate': 0}
        }
        
        self._connected = False
        self._device_info['connected'] = False
        
        logger.info("Disconnected from test KNX controller")
        return True
    
    def is_connected(self) -> bool:
        """Check if connected to test controller."""
        return self._connected
    
    def get_device_info(self) -> Dict[str, Any]:
        """Get simulated device information."""
        return self._device_info.copy()
    
    def get_capabilities(self) -> List[str]:
        """Get test HAL capabilities."""
        return [
            'valve_control',
            'pump_control',
            'flow_sensing',
            'temperature_monitoring',
            'hardware_status',
            'firmware_info',
            'multi_channel',
            'simulation_mode'
        ]
    
    # ========================================================================
    # Hardware Information Methods
    # ========================================================================
    
    def get_status(self) -> Optional[Dict[str, Any]]:
        """Get simulated hardware status."""
        if not self._connected:
            return None
            
        return {
            'device_ok': True,
            'temperature': 35.2,
            'pump_1_running': self._pump_states[1]['running'],
            'pump_2_running': self._pump_states[2]['running'],
            'valve_1_three_way': self._valve_states[1]['three_way'],
            'valve_1_six_port': self._valve_states[1]['six_port'],
            'valve_2_three_way': self._valve_states[2]['three_way'],
            'valve_2_six_port': self._valve_states[2]['six_port'],
            'system_time': int(time.time()),
            'uptime_sec': 3600
        }
    
    def get_info(self) -> Optional[Dict[str, Any]]:
        """Get simulated hardware information."""
        if not self._connected:
            return None
            
        return {
            'fw ver': self._device_info['firmware_version'],
            'hw ver': self._device_info['hardware_version'],
            'device': self._device_info['model'],
            'serial': self._device_info['serial_number'],
            'manufacturer': self._device_info['manufacturer'],
            'build_date': '2024-10-01',
            'capabilities': self.get_capabilities()
        }
    
    def get_parameters(self) -> Optional[Dict[str, Any]]:
        """Get simulated hardware parameters."""
        if not self._connected:
            return None
            
        return {
            'channels': 2,
            'max_flow_rate': 1000,  # ml/min
            'min_flow_rate': 1,     # ml/min
            'valve_types': ['three_way', 'six_port'],
            'led_channels': 4,
            'integration_time_ms': self._integration_time,
            'servo_mode': self._servo_mode,
            'temperature_range': {'min': -10, 'max': 80}
        }
    
    # ========================================================================
    # Valve Control Methods
    # ========================================================================
    
    def set_three_way_valve(self, channel: Union[str, int], state: int) -> bool:
        """Simulate three-way valve control."""
        if not self._connected:
            return False
            
        try:
            hw_channel = self._normalize_channel(channel)
            if state not in [0, 1]:
                logger.error(f"Invalid three-way valve state: {state}")
                return False
                
            self._valve_states[hw_channel]['three_way'] = state
            logger.debug(f"Test KNX: Set three-way valve CH{hw_channel} to {state}")
            time.sleep(0.05)  # Simulate valve movement delay
            return True
            
        except Exception as e:
            logger.exception(f"Error in test three-way valve control: {e}")
            return False
    
    def set_six_port_valve(self, channel: Union[str, int], state: int) -> bool:
        """Simulate six-port valve control."""
        if not self._connected:
            return False
            
        try:
            hw_channel = self._normalize_channel(channel)
            if state not in [0, 1]:
                logger.error(f"Invalid six-port valve state: {state}")
                return False
                
            self._valve_states[hw_channel]['six_port'] = state
            logger.debug(f"Test KNX: Set six-port valve CH{hw_channel} to {state}")
            time.sleep(0.1)  # Simulate valve movement delay
            return True
            
        except Exception as e:
            logger.exception(f"Error in test six-port valve control: {e}")
            return False
    
    def get_valve_status(self, channel: Union[str, int]) -> Optional[Dict[str, Any]]:
        """Get simulated valve status."""
        if not self._connected:
            return None
            
        try:
            hw_channel = self._normalize_channel(channel)
            valve_state = self._valve_states[hw_channel]
            
            return {
                'channel': hw_channel,
                'three_way_position': valve_state['three_way'],
                'six_port_position': valve_state['six_port'],
                'combined_position': self._get_combined_position(valve_state),
                'last_movement': time.time(),
                'operational': True
            }
            
        except Exception as e:
            logger.exception(f"Error getting test valve status: {e}")
            return None
    
    # ========================================================================
    # Pump Control Methods
    # ========================================================================
    
    def start_pump(self, channel: Union[str, int], rate: int) -> bool:
        """Simulate pump start."""
        if not self._connected:
            return False
            
        try:
            hw_channel = self._normalize_channel(channel)
            if rate <= 0:
                logger.error(f"Invalid pump rate: {rate}")
                return False
                
            self._pump_states[hw_channel]['running'] = True
            self._pump_states[hw_channel]['rate'] = rate
            
            # Simulate flow rate for sensors
            if hw_channel == 1:
                self._flow_rate_ch1 = rate
            else:
                self._flow_rate_ch2 = rate
                
            logger.debug(f"Test KNX: Started pump CH{hw_channel} at rate {rate}")
            return True
            
        except Exception as e:
            logger.exception(f"Error in test pump start: {e}")
            return False
    
    def stop_pump(self, channel: Union[str, int]) -> bool:
        """Simulate pump stop."""
        if not self._connected:
            return False
            
        try:
            hw_channel = self._normalize_channel(channel)
            
            self._pump_states[hw_channel]['running'] = False
            self._pump_states[hw_channel]['rate'] = 0
            
            # Stop simulated flow
            if hw_channel == 1:
                self._flow_rate_ch1 = 0.0
            else:
                self._flow_rate_ch2 = 0.0
                
            logger.debug(f"Test KNX: Stopped pump CH{hw_channel}")
            return True
            
        except Exception as e:
            logger.exception(f"Error in test pump stop: {e}")
            return False
    
    def stop_all_pumps(self) -> bool:
        """Simulate emergency stop all pumps."""
        if not self._connected:
            return False
            
        try:
            for channel in [1, 2]:
                self._pump_states[channel]['running'] = False
                self._pump_states[channel]['rate'] = 0
                
            self._flow_rate_ch1 = 0.0
            self._flow_rate_ch2 = 0.0
            
            logger.debug("Test KNX: Emergency stopped all pumps")
            return True
            
        except Exception as e:
            logger.exception(f"Error in test emergency stop: {e}")
            return False
    
    # ========================================================================
    # LED Control Methods
    # ========================================================================
    
    def turn_on_led(self, channel: str = 'a') -> bool:
        """Simulate LED control."""
        if not self._connected:
            return False
            
        try:
            ch_map = {'a': 1, 'b': 2, 'c': 3, 'd': 4}
            if channel not in ch_map:
                logger.error(f"Invalid LED channel: {channel}")
                return False
                
            led_num = ch_map[channel]
            self._led_states[led_num]['on'] = True
            logger.debug(f"Test KNX: Turned on LED {channel}")
            return True
            
        except Exception as e:
            logger.exception(f"Error in test LED control: {e}")
            return False
    
    def turn_off_leds(self) -> bool:
        """Simulate turning off all LEDs."""
        if not self._connected:
            return False
            
        try:
            for led_num in self._led_states:
                self._led_states[led_num]['on'] = False
                
            logger.debug("Test KNX: Turned off all LEDs")
            return True
            
        except Exception as e:
            logger.exception(f"Error turning off test LEDs: {e}")
            return False
    
    def set_led_intensity(self, channel: str = 'a', intensity: int = 255) -> bool:
        """Simulate LED intensity control."""
        if not self._connected:
            return False
            
        try:
            ch_map = {'a': 1, 'b': 2, 'c': 3, 'd': 4}
            if channel not in ch_map:
                logger.error(f"Invalid LED channel: {channel}")
                return False
                
            led_num = ch_map[channel]
            self._led_states[led_num]['intensity'] = intensity
            self._led_states[led_num]['on'] = True
            
            logger.debug(f"Test KNX: Set LED {channel} intensity to {intensity}")
            return True
            
        except Exception as e:
            logger.exception(f"Error in test LED intensity: {e}")
            return False
    
    # ========================================================================
    # Data Reading Methods
    # ========================================================================
    
    def read_wavelength(self, channel: Union[str, int]) -> Optional[List[int]]:
        """Simulate wavelength data reading."""
        if not self._connected:
            return None
            
        try:
            hw_channel = self._normalize_channel(channel)
            
            # Generate simulated wavelength data
            import random
            base_wavelength = 630 if hw_channel == 1 else 850
            wavelengths = []
            
            for i in range(10):  # Simulate 10 data points
                noise = random.randint(-5, 5)
                wavelengths.append(base_wavelength + i * 10 + noise)
                
            logger.debug(f"Test KNX: Read wavelength data for CH{hw_channel}")
            return wavelengths
            
        except Exception as e:
            logger.exception(f"Error reading test wavelength data: {e}")
            return None
    
    def read_intensity(self) -> Optional[List[int]]:
        """Simulate intensity data reading."""
        if not self._connected:
            return None
            
        try:
            # Generate simulated intensity data
            import random
            intensities = []
            
            for i in range(10):  # Simulate 10 data points
                base_intensity = 1000 + i * 50
                noise = random.randint(-20, 20)
                intensities.append(base_intensity + noise)
                
            logger.debug("Test KNX: Read intensity data")
            return intensities
            
        except Exception as e:
            logger.exception(f"Error reading test intensity data: {e}")
            return None
    
    # ========================================================================
    # Configuration Methods
    # ========================================================================
    
    def set_integration_time(self, time_ms: int) -> bool:
        """Simulate integration time setting."""
        if not self._connected:
            return False
            
        try:
            if time_ms <= 0:
                logger.error(f"Invalid integration time: {time_ms}")
                return False
                
            self._integration_time = time_ms
            logger.debug(f"Test KNX: Set integration time to {time_ms}ms")
            return True
            
        except Exception as e:
            logger.exception(f"Error setting test integration time: {e}")
            return False
    
    def set_servo_mode(self, mode: str = 's') -> bool:
        """Simulate servo mode setting."""
        if not self._connected:
            return False
            
        try:
            self._servo_mode = mode
            logger.debug(f"Test KNX: Set servo mode to {mode}")
            return True
            
        except Exception as e:
            logger.exception(f"Error setting test servo mode: {e}")
            return False
    
    def set_servo_position(self, speed: int = 10, position: int = 100) -> bool:
        """Simulate servo position setting."""
        if not self._connected:
            return False
            
        try:
            self._servo_position = {'speed': speed, 'position': position}
            logger.debug(f"Test KNX: Set servo position speed={speed}, pos={position}")
            return True
            
        except Exception as e:
            logger.exception(f"Error setting test servo position: {e}")
            return False
    
    def stop_system(self) -> bool:
        """Simulate system stop."""
        if not self._connected:
            return False
            
        try:
            # Stop all pumps
            self.stop_all_pumps()
            
            # Reset valves to safe positions
            for channel in [1, 2]:
                self._valve_states[channel] = {'three_way': 0, 'six_port': 0}
                
            logger.debug("Test KNX: System stopped")
            return True
            
        except Exception as e:
            logger.exception(f"Error in test system stop: {e}")
            return False
    
    # ========================================================================
    # Test-Specific Methods
    # ========================================================================
    
    def simulate_temperature_change(self, channel: int, temperature: float) -> None:
        """
        Simulate temperature change for testing.
        
        Args:
            channel: Channel number (1 or 2)
            temperature: New temperature value
        """
        if channel == 1:
            self._temperature_ch1 = temperature
        elif channel == 2:
            self._temperature_ch2 = temperature
            
        logger.debug(f"Test KNX: Simulated temperature change CH{channel}: {temperature}°C")
    
    def get_simulated_sensor_data(self) -> Dict[str, float]:
        """
        Get current simulated sensor data.
        
        Returns:
            Dictionary with sensor readings
        """
        return {
            'temperature_ch1': self._temperature_ch1,
            'temperature_ch2': self._temperature_ch2,
            'flow_rate_ch1': self._flow_rate_ch1,
            'flow_rate_ch2': self._flow_rate_ch2
        }
    
    # ========================================================================
    # Private Helper Methods
    # ========================================================================
    
    def _normalize_channel(self, channel: Union[str, int]) -> int:
        """Normalize channel identifier to hardware channel number."""
        if isinstance(channel, int):
            if channel in [1, 2]:
                return channel
        elif isinstance(channel, str):
            if channel.upper() in ["CH1", "1"]:
                return 1
            elif channel.upper() in ["CH2", "2"]:
                return 2
                
        raise ValueError(f"Invalid channel identifier: {channel}")
    
    def _get_combined_position(self, valve_state: Dict[str, int]) -> str:
        """Get combined valve position name."""
        three_way = valve_state['three_way']
        six_port = valve_state['six_port']
        
        if three_way == 0 and six_port == 0:
            return "WASTE"
        elif three_way == 1 and six_port == 0:
            return "LOAD"
        elif three_way == 1 and six_port == 1:
            return "INJECT"
        elif three_way == 0 and six_port == 1:
            return "DISPOSE"
        else:
            return "UNKNOWN"