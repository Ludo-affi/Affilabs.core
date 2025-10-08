"""
Kinetic System Hardware Abstraction Layer

Provides a unified interface for kinetic systems (pumps, valves, etc.)
used in SPR measurements. This is a placeholder implementation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from .hal_exceptions import HALError


class PumpDirection(Enum):
    """Pump flow directions."""
    FORWARD = "forward"
    REVERSE = "reverse"
    STOP = "stop"


class ValvePosition(Enum):
    """Valve positions."""
    POSITION_A = "A"
    POSITION_B = "B" 
    POSITION_C = "C"
    POSITION_D = "D"
    POSITION_E = "E"
    POSITION_F = "F"


@dataclass
class KineticCapabilities:
    """Describes capabilities of a kinetic system."""
    
    # Pump capabilities
    num_pumps: int
    max_flow_rate: float  # μL/min
    min_flow_rate: float  # μL/min
    supports_bidirectional: bool
    
    # Valve capabilities
    num_valves: int
    valve_positions: List[ValvePosition]
    
    # Control features
    supports_synchronization: bool
    supports_flow_feedback: bool
    
    # Connection
    connection_type: str
    device_model: str


class KineticSystemHAL(ABC):
    """
    Hardware Abstraction Layer for Kinetic Systems.
    
    This is a placeholder implementation demonstrating the interface
    pattern for pump and valve control systems.
    """
    
    def __init__(self, device_name: str) -> None:
        """Initialize kinetic system HAL."""
        self.device_name = device_name
    
    @abstractmethod
    def connect(self, **connection_params: Any) -> bool:
        """Connect to kinetic system."""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from kinetic system."""
        pass
    
    @abstractmethod
    def control_pump(
        self, 
        pump_id: int, 
        flow_rate: float, 
        direction: PumpDirection = PumpDirection.FORWARD
    ) -> bool:
        """Control pump operation."""
        pass
    
    @abstractmethod
    def set_valve_position(self, valve_id: int, position: ValvePosition) -> bool:
        """Set valve position."""
        pass
    
    @abstractmethod
    def get_pump_status(self, pump_id: int) -> Dict[str, Any]:
        """Get pump status information."""
        pass
    
    @abstractmethod
    def get_valve_status(self, valve_id: int) -> Dict[str, Any]:
        """Get valve status information."""
        pass
    
    def get_capabilities(self) -> KineticCapabilities:
        """Get kinetic system capabilities."""
        return self._define_capabilities()
    
    @abstractmethod
    def _define_capabilities(self) -> KineticCapabilities:
        """Define capabilities for this kinetic system type."""
        pass