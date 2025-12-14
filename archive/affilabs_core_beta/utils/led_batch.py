"""LED Batch Command Builder

Provides convenient methods for creating and executing batch LED commands.
This makes it easy to optimize LED operations when multiple parameters need to be set.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from utils.hal.interfaces import LEDCommand, LEDController
from utils.logger import logger


class LEDBatchBuilder:
    """Builder pattern for constructing batch LED commands"""
    
    def __init__(self):
        self._commands: List[LEDCommand] = []
    
    def set_mode(self, mode: str) -> 'LEDBatchBuilder':
        """Add mode change command to batch
        
        Args:
            mode: 's' for S-polarized, 'p' for P-polarized
        """
        self._commands.append(LEDCommand('mode', mode=mode))
        return self
    
    def set_intensity(self, channel: str, intensity: int) -> 'LEDBatchBuilder':
        """Add intensity change command to batch
        
        Args:
            channel: 'a', 'b', 'c', or 'd'
            intensity: 0-255
        """
        self._commands.append(LEDCommand('intensity', channel=channel, intensity=intensity))
        return self
    
    def turn_on(self, channel: str) -> 'LEDBatchBuilder':
        """Add turn on command to batch
        
        Args:
            channel: 'a', 'b', 'c', or 'd'
        """
        self._commands.append(LEDCommand('on', channel=channel))
        return self
    
    def turn_off_all(self) -> 'LEDBatchBuilder':
        """Add turn off all channels command to batch"""
        self._commands.append(LEDCommand('off'))
        return self
    
    def execute(self, led_controller: LEDController) -> bool:
        """Execute all batched commands
        
        Args:
            led_controller: LED controller HAL instance
            
        Returns:
            True if batch execution successful
        """
        if not self._commands:
            logger.warning("No commands in batch to execute")
            return True
        
        try:
            result = led_controller.execute_batch(self._commands)
            self._commands.clear()  # Clear after execution
            return result
        except Exception as e:
            logger.error(f"Batch execution failed: {e}")
            self._commands.clear()
            return False
    
    def clear(self) -> 'LEDBatchBuilder':
        """Clear all pending commands"""
        self._commands.clear()
        return self
    
    @property
    def commands(self) -> List[LEDCommand]:
        """Get current list of commands"""
        return self._commands.copy()


def create_calibration_batch(mode: str, intensities: Dict[str, int]) -> List[LEDCommand]:
    """Create a batch for calibration setup (mode + all intensities)
    
    Args:
        mode: 's' or 'p'
        intensities: Dict mapping channel -> intensity (e.g., {'a': 180, 'b': 200, 'c': 150, 'd': 100})
    
    Returns:
        List of LED commands
    """
    commands = [LEDCommand('mode', mode=mode)]
    for ch, intensity in intensities.items():
        commands.append(LEDCommand('intensity', channel=ch, intensity=intensity))
    return commands


def create_measurement_batch(mode: str, channel: str, intensity: int) -> List[LEDCommand]:
    """Create a batch for single channel measurement (mode + intensity)
    
    Args:
        mode: 's' or 'p'
        channel: 'a', 'b', 'c', or 'd'
        intensity: 0-255
    
    Returns:
        List of LED commands
    """
    return [
        LEDCommand('mode', mode=mode),
        LEDCommand('intensity', channel=channel, intensity=intensity)
    ]


# Example usage patterns:
"""
# Pattern 1: Using builder (fluent interface)
batch = LEDBatchBuilder()
batch.set_mode('s').set_intensity('a', 180).set_intensity('b', 200).execute(led_controller)

# Pattern 2: Using helper functions
commands = create_calibration_batch('p', {'a': 180, 'b': 200, 'c': 150, 'd': 100})
led_controller.execute_batch(commands)

# Pattern 3: Manual command list
commands = [
    LEDCommand('mode', mode='s'),
    LEDCommand('intensity', channel='a', intensity=180),
    LEDCommand('intensity', channel='b', intensity=200),
]
led_controller.execute_batch(commands)

# Pattern 4: Check capabilities first
caps = led_controller.get_capabilities()
if caps.get('supports_batch', False):
    # Use optimized batch
    batch.set_mode('s').set_intensity('a', 180).set_intensity('b', 200).execute(led_controller)
else:
    # Fall back to individual commands
    led_controller.set_mode('s')
    led_controller.set_intensity('a', 180)
    led_controller.set_intensity('b', 200)
"""
