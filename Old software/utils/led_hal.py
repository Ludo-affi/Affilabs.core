"""LED Hardware Abstraction Layer

Provides unified interface for LED control with support for:
- Individual LED commands (current behavior)
- Batch LED commands (optimized for performance)
- Multiple LED controller types
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from enum import Enum

from utils.logger import logger


class LEDMode(Enum):
    """LED polarization modes"""
    S_POLARIZED = "s"
    P_POLARIZED = "p"


class LEDCommand:
    """Represents a single LED operation"""
    
    def __init__(self, action: str, channel: Optional[str] = None, 
                 intensity: Optional[int] = None, mode: Optional[LEDMode] = None):
        self.action = action  # 'on', 'off', 'intensity', 'mode'
        self.channel = channel
        self.intensity = intensity
        self.mode = mode
    
    def __repr__(self):
        return f"LEDCommand({self.action}, ch={self.channel}, int={self.intensity}, mode={self.mode})"


class LEDControllerHAL(ABC):
    """Abstract base class for LED controllers"""
    
    @abstractmethod
    def turn_on_channel(self, ch: str) -> bool:
        """Turn on a specific LED channel.
        
        Args:
            ch: Channel identifier ('a', 'b', 'c', 'd')
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def turn_off_channels(self) -> bool:
        """Turn off all LED channels.
        
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def set_intensity(self, ch: str, intensity: int) -> bool:
        """Set LED intensity for a channel.
        
        Args:
            ch: Channel identifier
            intensity: LED brightness (0-255)
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def set_mode(self, mode: str) -> bool:
        """Set LED polarization mode.
        
        Args:
            mode: 's' for S-polarized, 'p' for P-polarized
            
        Returns:
            True if successful
        """
        pass
    
    def execute_batch(self, commands: List[LEDCommand]) -> bool:
        """Execute a batch of LED commands.
        
        Default implementation executes sequentially. Override for optimized batch processing.
        
        Args:
            commands: List of LED commands to execute
            
        Returns:
            True if all commands successful
        """
        for cmd in commands:
            if cmd.action == 'on':
                if not self.turn_on_channel(cmd.channel):
                    return False
            elif cmd.action == 'off':
                if not self.turn_off_channels():
                    return False
            elif cmd.action == 'intensity':
                if not self.set_intensity(cmd.channel, cmd.intensity):
                    return False
            elif cmd.action == 'mode':
                if not self.set_mode(cmd.mode.value if isinstance(cmd.mode, LEDMode) else cmd.mode):
                    return False
        return True
    
    @abstractmethod
    def get_capabilities(self) -> Dict[str, any]:
        """Get controller capabilities.
        
        Returns:
            Dictionary with capabilities (supports_batch, max_intensity, etc.)
        """
        pass


class PicoP4SPRLEDController(LEDControllerHAL):
    """LED HAL implementation for Pico P4SPR controller"""
    
    def __init__(self, controller):
        """Initialize with existing controller instance.
        
        Args:
            controller: PicoP4SPR controller instance with serial interface
        """
        self._ctrl = controller
        self._current_mode = LEDMode.S_POLARIZED
        self._current_intensities = {'a': 255, 'b': 255, 'c': 255, 'd': 255}
        logger.debug("Initialized PicoP4SPR LED HAL")
    
    def turn_on_channel(self, ch: str) -> bool:
        """Turn on specific LED channel using controller's method"""
        try:
            return self._ctrl.turn_on_channel(ch=ch)
        except Exception as e:
            logger.error(f"Failed to turn on channel {ch}: {e}")
            return False
    
    def turn_off_channels(self) -> bool:
        """Turn off all channels using controller's method"""
        try:
            return self._ctrl.turn_off_channels()
        except Exception as e:
            logger.error(f"Failed to turn off channels: {e}")
            return False
    
    def set_intensity(self, ch: str, intensity: int) -> bool:
        """Set LED intensity using controller's method"""
        try:
            result = self._ctrl.set_intensity(ch=ch, raw_val=intensity)
            if result:
                self._current_intensities[ch] = intensity
            return result
        except Exception as e:
            logger.error(f"Failed to set intensity for {ch}: {e}")
            return False
    
    def set_mode(self, mode: str) -> bool:
        """Set polarization mode using controller's method"""
        try:
            result = self._ctrl.set_mode(mode)
            if result:
                self._current_mode = LEDMode.S_POLARIZED if mode == 's' else LEDMode.P_POLARIZED
            return result
        except Exception as e:
            logger.error(f"Failed to set mode {mode}: {e}")
            return False
    
    def execute_batch(self, commands: List[LEDCommand]) -> bool:
        """Execute batch commands with optimized protocol.
        
        Pico P4SPR supports batch LED commands in format:
        lb<mode><ch_a><int_a><ch_b><int_b>...\n
        
        Example: lbs255a180b200c150d100\n
        Sets S-mode with A=180, B=200, C=150, D=100
        """
        try:
            # Check if we can optimize this into a single batch command
            # Batch command is useful when setting multiple channels at once
            
            # Analyze commands to see if they can be batched
            has_mode = False
            has_intensities = {}
            has_turn_on = []
            
            for cmd in commands:
                if cmd.action == 'mode':
                    has_mode = cmd.mode
                elif cmd.action == 'intensity':
                    has_intensities[cmd.channel] = cmd.intensity
                elif cmd.action == 'on':
                    has_turn_on.append(cmd.channel)
            
            # If we have mode + multiple intensities, use batch command
            if has_mode and len(has_intensities) >= 2:
                mode_char = has_mode.value if isinstance(has_mode, LEDMode) else has_mode
                
                # Build batch command: lb<mode><intensity><ch_a><int_a><ch_b><int_b>...
                batch_cmd = f"lb{mode_char}255"  # Start with mode and default intensity
                
                for ch in ['a', 'b', 'c', 'd']:
                    if ch in has_intensities:
                        batch_cmd += f"{ch}{has_intensities[ch]:03d}"
                
                batch_cmd += "\n"
                
                # Send batch command
                if self._ctrl._ser is not None:
                    with self._ctrl._lock:
                        self._ctrl._ser.write(batch_cmd.encode())
                        response = self._ctrl._ser.readline().strip()
                        
                        if response == b'1':
                            logger.debug(f"Batch LED command successful: {batch_cmd.strip()}")
                            # Update cached state
                            self._current_mode = has_mode
                            self._current_intensities.update(has_intensities)
                            return True
                        else:
                            logger.warning(f"Batch LED command failed, response: {response}")
                            return False
                else:
                    logger.error("Serial port not open for batch command")
                    return False
            else:
                # Fall back to sequential execution
                return super().execute_batch(commands)
                
        except Exception as e:
            logger.error(f"Batch LED command failed: {e}")
            # Fall back to sequential
            return super().execute_batch(commands)
    
    def get_capabilities(self) -> Dict[str, any]:
        """Return Pico P4SPR capabilities"""
        return {
            'supports_batch': True,
            'max_intensity': 255,
            'channels': ['a', 'b', 'c', 'd'],
            'modes': ['s', 'p'],
            'batch_protocol': 'lb',
        }


class ArduinoLEDController(LEDControllerHAL):
    """LED HAL implementation for Arduino-based controllers"""
    
    def __init__(self, controller):
        """Initialize with existing Arduino controller instance"""
        self._ctrl = controller
        logger.debug("Initialized Arduino LED HAL")
    
    def turn_on_channel(self, ch: str) -> bool:
        """Turn on specific LED channel"""
        try:
            return self._ctrl.turn_on_channel(ch=ch)
        except Exception as e:
            logger.error(f"Failed to turn on channel {ch}: {e}")
            return False
    
    def turn_off_channels(self) -> bool:
        """Turn off all channels"""
        try:
            return self._ctrl.turn_off_channels()
        except Exception as e:
            logger.error(f"Failed to turn off channels: {e}")
            return False
    
    def set_intensity(self, ch: str, intensity: int) -> bool:
        """Set LED intensity"""
        try:
            return self._ctrl.set_intensity(ch=ch, raw_val=intensity)
        except Exception as e:
            logger.error(f"Failed to set intensity for {ch}: {e}")
            return False
    
    def set_mode(self, mode: str) -> bool:
        """Set polarization mode"""
        try:
            return self._ctrl.set_mode(mode)
        except Exception as e:
            logger.error(f"Failed to set mode {mode}: {e}")
            return False
    
    def get_capabilities(self) -> Dict[str, any]:
        """Return Arduino capabilities"""
        return {
            'supports_batch': False,  # Arduino doesn't support batch commands
            'max_intensity': 255,
            'channels': ['a', 'b', 'c', 'd'],
            'modes': ['s', 'p'],
        }


def create_led_hal(controller) -> LEDControllerHAL:
    """Factory function to create appropriate LED HAL for controller type.
    
    Args:
        controller: Controller instance (PicoP4SPR, Arduino, etc.)
        
    Returns:
        Appropriate LED HAL implementation
    """
    controller_type = type(controller).__name__
    
    if 'PicoP4SPR' in controller_type or 'PicoEZSPR' in controller_type:
        return PicoP4SPRLEDController(controller)
    elif 'Arduino' in controller_type:
        return ArduinoLEDController(controller)
    else:
        logger.warning(f"Unknown controller type {controller_type}, using PicoP4SPR LED HAL")
        return PicoP4SPRLEDController(controller)
