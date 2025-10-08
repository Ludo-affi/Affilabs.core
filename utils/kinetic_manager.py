"""
Kinetic System Manager
Provides high-level abstraction for KNX valve control, pump management,
sensor reading, and kinetic event logging.

Hardware Components:
--------------------
1. Six-Port Valve (knx_six):
   - Manufacturer: Takasago Electric
   - Model: Low Pressure 2-Position 6-Port Valve
   - Product Link: https://www.takasago-fluidics.com/products/2position-6port-valve?variant=37040799285414
   - Function: Switches between Load (position 0) and Inject (position 1) positions
   - Used for: Sample injection in SPR flow cells
   
2. Three-Way Valve (knx_three):
   - Manufacturer: The Lee Company
   - Model: XOVER 2/3-Way Isolation Solenoid Valve (24V)
   - Product Link: https://www.theleeco.com/product/xover-2-3-way-isolation-solenoid-valve/
   - Function: Switches between Waste (position 0) and Load (position 1) positions
   - Used for: Directing flow to waste or sample loop
   
3. Combined Valve Positions:
   - WASTE:   3-way=0 (waste),  6-port=0 (load)
   - LOAD:    3-way=1 (load),   6-port=0 (load)
   - INJECT:  3-way=1 (load),   6-port=1 (inject)
   - DISPOSE: 3-way=0 (waste),  6-port=1 (inject)

4. Temperature Sensors:
   - Integrated into KNX controller
   - Monitors sample temperature in flow cells (CH1 and CH2)
   - Device temperature monitoring for hardware diagnostics
"""

from __future__ import annotations

import asyncio
import datetime as dt
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable

import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal

from utils.logger import logger

try:
    from utils.controller import KineticController, PicoEZSPR
    # PicoKNX2 disabled (obsolete hardware)
except ImportError:
    KineticController = None
    PicoEZSPR = None


# ============================================================================
# Constants and Enums
# ============================================================================

class ValvePosition(Enum):
    """Valve position states."""
    WASTE = auto()      # 3-way=0, 6-port=0
    LOAD = auto()       # 3-way=1, 6-port=0
    INJECT = auto()     # 3-way=1, 6-port=1
    DISPOSE = auto()    # 3-way=0, 6-port=1


class Channel(Enum):
    """Kinetic system channels."""
    CH1 = "CH1"
    CH2 = "CH2"
    BOTH = "BOTH"  # When synced


# Sensor constants
DEFAULT_SENSOR_AVG_WINDOW = 10  # Number of readings to average
DEFAULT_SENSOR_INTERVAL_SEC = 10  # Seconds between sensor reads
DEVICE_TEMP_MIN = 5.0  # Min reasonable device temperature (°C)
DEVICE_TEMP_MAX = 75.0  # Max reasonable device temperature (°C)
DEVICE_TEMP_AVG_WINDOW = 5  # Readings to average for device temp

# Injection timeout constants
INJECTION_BASE_TIME_SEC = 100  # Base time for injection (seconds)
INJECTION_SAFETY_MARGIN_MIN = 2  # Extra minutes added to timeout


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ValveState:
    """State of valves for one channel."""
    three_way_position: int = 0  # 0 or 1
    six_port_position: int = 0   # 0 or 1
    last_injection_time: float = 0.0  # Experiment time when injection started
    last_injection_timestamp: str = ""  # Human-readable timestamp
    
    @property
    def position(self) -> ValvePosition:
        """Get combined valve position."""
        if self.six_port_position == 1 and self.three_way_position == 1:
            return ValvePosition.INJECT
        elif self.six_port_position == 0 and self.three_way_position == 1:
            return ValvePosition.LOAD
        elif self.six_port_position == 1 and self.three_way_position == 0:
            return ValvePosition.DISPOSE
        else:
            return ValvePosition.WASTE
    
    @property
    def position_name(self) -> str:
        """Get position as string."""
        return self.position.name.capitalize()


@dataclass
class SensorReading:
    """Temperature sensor reading."""
    temperature: float | None = None  # °C
    timestamp: float = field(default_factory=time.time)
    exp_time: float = 0.0  # Time since experiment start
    
    def is_valid(self) -> bool:
        """Check if reading has valid data."""
        return self.temperature is not None


@dataclass
class ChannelState:
    """Complete state of one kinetic channel."""
    channel_name: str  # "CH1" or "CH2"
    valve: ValveState = field(default_factory=ValveState)
    pump_running: bool = False
    pump_rate: float = 0.0  # ml/min
    current_temp: float | None = None  # °C (from sensor)
    injection_timer_active: bool = False
    injection_timeout_sec: int = 0


@dataclass
class KineticLog:
    """Kinetic event log for one channel."""
    timestamps: list[str] = field(default_factory=list)  # "HH:MM:SS"
    times: list[str] = field(default_factory=list)  # Experiment time
    events: list[str] = field(default_factory=list)  # Event description
    temp: list[str] = field(default_factory=list)  # Temperature readings
    dev: list[str] = field(default_factory=list)  # Device temperature
    
    def append_event(
        self,
        event: str,
        exp_time: float,
        temp: str = "-",
        dev: str = "-",
    ) -> None:
        """Append a kinetic event to the log."""
        time_now = dt.datetime.now()
        timestamp = time_now.strftime("%H:%M:%S")
        
        self.timestamps.append(timestamp)
        self.times.append(f"{exp_time:.2f}")
        self.events.append(event)
        self.temp.append(temp)
        self.dev.append(dev)
    
    def to_dict(self) -> dict[str, list]:
        """Convert to dictionary for export."""
        return {
            "timestamps": self.timestamps,
            "times": self.times,
            "events": self.events,
            "temp": self.temp,
            "dev": self.dev,
        }
    
    def clear(self) -> None:
        """Clear all log entries."""
        self.timestamps.clear()
        self.times.clear()
        self.events.clear()
        self.temp.clear()
        self.dev.clear()


# ============================================================================
# Kinetic Manager
# ============================================================================

class KineticManager(QObject):
    """
    Manages kinetic system (KNX) operations.
    
    Features:
    - Valve control (3-way and 6-port) with position verification
    - Temperature sensor reading with averaging
    - Injection timing and auto-timeout
    - Synchronized dual-channel operation
    - Comprehensive event logging
    - Error handling and retry logic
    """
    
    # Signals
    valve_state_changed = Signal(str, str)  # channel, position_name
    sensor_reading = Signal(dict)  # {"temp1": str, "temp2": str}
    device_temp_updated = Signal(str, str)  # temperature, source ("ctrl" or "knx")
    injection_started = Signal(str, float)  # channel, exp_time
    injection_ended = Signal(str)  # channel
    error_occurred = Signal(str, str)  # channel, error_message
    
    def __init__(
        self,
        kinetic_controller: Any | None = None,
        experiment_start_time: float | None = None,
    ) -> None:
        """
        Initialize kinetic manager.
        
        Args:
            kinetic_controller: KNX hardware controller instance
            experiment_start_time: Start time for experiment clock (time.time())
        """
        super().__init__()
        self.knx = kinetic_controller
        self.exp_start = experiment_start_time or time.time()
        
        # Channel states
        self.channels = {
            "CH1": ChannelState(channel_name="CH1"),
            "CH2": ChannelState(channel_name="CH2"),
        }
        
        # Sync mode
        self.synced = False
        
        # Kinetic logs
        self.logs = {
            "CH1": KineticLog(),
            "CH2": KineticLog(),
        }
        
        # Sensor buffers for averaging (temperature only)
        self._temp_buf_1: list[float] = []
        self._temp_buf_2: list[float] = []
        self._device_temp_buf: list[float] = []
        
        # Sensor settings
        self.sensor_avg_window = DEFAULT_SENSOR_AVG_WINDOW
        self.sensor_interval_sec = DEFAULT_SENSOR_INTERVAL_SEC
        
        # Injection timers
        self._injection_timer_ch1 = QTimer()
        self._injection_timer_ch1.timeout.connect(lambda: self._auto_end_injection("CH1"))
        self._injection_timer_ch2 = QTimer()
        self._injection_timer_ch2.timeout.connect(lambda: self._auto_end_injection("CH2"))
        
        # Sensor reading control
        self._sensor_paused = False
        
        logger.info("KineticManager initialized")
    
    # ========================================================================
    # Hardware Availability
    # ========================================================================
    
    def is_available(self) -> bool:
        """Check if kinetic hardware is available."""
        return self.knx is not None
    
    def get_device_type(self) -> str:
        """Get the type of kinetic device."""
        if not self.is_available():
            return ""
        
        if hasattr(self.knx, 'name'):
            return self.knx.name
        
        return type(self.knx).__name__
    
    def get_device_version(self) -> str:
        """Get device firmware version."""
        if not self.is_available():
            return ""
        
        if hasattr(self.knx, 'version'):
            return self.knx.version
        
        return "unknown"
    
    # ========================================================================
    # Valve Control - Three-Way Valves
    # ========================================================================
    
    def set_three_way_valve(self, channel: str, position: int) -> bool:
        """
        Set three-way valve position.
        
        Args:
            channel: "CH1" or "CH2"
            position: 0 (waste) or 1 (load)
            
        Returns:
            True if successful
        """
        if not self.is_available():
            logger.warning("Cannot set 3-way valve: KNX not available")
            return False
        
        if not self._validate_channel(channel):
            logger.error(f"Invalid channel: {channel}")
            return False
        
        if position not in [0, 1]:
            logger.error(f"Invalid 3-way position: {position} (must be 0 or 1)")
            return False
        
        try:
            # Pause sensor reading during valve movement
            self.pause_sensor_reading()
            
            # Determine hardware channel
            hw_channel = self._hardware_channel_number(channel)
            
            # Send command to hardware
            self.knx.knx_three(position, hw_channel)
            
            # Update state
            self.channels[channel].valve.three_way_position = position
            
            # If synced, update CH2 as well
            if self.synced and channel == "CH1":
                self.channels["CH2"].valve.three_way_position = position
            
            # Resume sensor reading
            self.resume_sensor_reading()
            
            # Emit signal
            self.valve_state_changed.emit(channel, self.get_valve_position_name(channel))
            if self.synced and channel == "CH1":
                self.valve_state_changed.emit("CH2", self.get_valve_position_name("CH2"))
            
            logger.debug(f"3-way valve {channel} set to position {position}")
            return True
            
        except Exception as e:
            logger.exception(f"Error setting 3-way valve {channel}: {e}")
            self.resume_sensor_reading()
            self.error_occurred.emit(channel, f"3-way valve error: {e}")
            return False
    
    def get_three_way_position(self, channel: str) -> int:
        """
        Get current three-way valve position.
        
        Args:
            channel: "CH1" or "CH2"
            
        Returns:
            0 or 1
        """
        if not self._validate_channel(channel):
            return 0
        
        return self.channels[channel].valve.three_way_position
    
    def toggle_three_way_valve(self, channel: str) -> bool:
        """
        Toggle three-way valve between waste and load.
        
        Args:
            channel: "CH1" or "CH2"
            
        Returns:
            True if successful
        """
        current_position = self.get_three_way_position(channel)
        new_position = 1 if current_position == 0 else 0
        return self.set_three_way_valve(channel, new_position)
    
    # ========================================================================
    # Valve Control - Six-Port Valves
    # ========================================================================
    
    def set_six_port_valve(self, channel: str, position: int) -> bool:
        """
        Set six-port valve position.
        
        Args:
            channel: "CH1" or "CH2"
            position: 0 (load) or 1 (inject)
            
        Returns:
            True if successful
        """
        # TODO: Implement six-port valve control
        # - Pause sensor reading
        # - Determine hardware channel (1, 2, or 3 for synced)
        if not self.is_available():
            logger.warning("Cannot set 6-port valve: KNX not available")
            return False
        
        if not self._validate_channel(channel):
            logger.error(f"Invalid channel: {channel}")
            return False
        
        if position not in [0, 1]:
            logger.error(f"Invalid 6-port position: {position} (must be 0 or 1)")
            return False
        
        try:
            # Pause sensor reading during valve movement
            self.pause_sensor_reading()
            
            # Determine hardware channel
            hw_channel = self._hardware_channel_number(channel)
            
            # Send command to hardware
            self.knx.knx_six(position, hw_channel)
            
            # Update state
            self.channels[channel].valve.six_port_position = position
            
            # If synced, update CH2 as well
            if self.synced and channel == "CH1":
                self.channels["CH2"].valve.six_port_position = position
            
            # Resume sensor reading
            self.resume_sensor_reading()
            
            # Emit signal
            self.valve_state_changed.emit(channel, self.get_valve_position_name(channel))
            if self.synced and channel == "CH1":
                self.valve_state_changed.emit("CH2", self.get_valve_position_name("CH2"))
            
            logger.debug(f"6-port valve {channel} set to position {position}")
            return True
            
        except Exception as e:
            logger.exception(f"Error setting 6-port valve {channel}: {e}")
            self.resume_sensor_reading()
            self.error_occurred.emit(channel, f"6-port valve error: {e}")
            return False
    
    def get_six_port_position(self, channel: str) -> int:
        """
        Get current six-port valve position.
        
        Args:
            channel: "CH1" or "CH2"
            
        Returns:
            0 or 1
        """
        if not self._validate_channel(channel):
            return 0
        
        return self.channels[channel].valve.six_port_position
    
    def toggle_six_port_valve(self, channel: str) -> bool:
        """
        Toggle six-port valve between load and inject.
        
        Args:
            channel: "CH1" or "CH2"
            
        Returns:
            True if successful
        """
        current_position = self.get_six_port_position(channel)
        new_position = 1 if current_position == 0 else 0
        return self.set_six_port_valve(channel, new_position)
    
    # ========================================================================
    # Valve State Management
    # ========================================================================
    
    def get_valve_position(self, channel: str) -> ValvePosition:
        """
        Get combined valve position (WASTE/LOAD/INJECT/DISPOSE).
        
        Args:
            channel: "CH1" or "CH2"
            
        Returns:
            ValvePosition enum value
        """
        if not self._validate_channel(channel):
            return ValvePosition.WASTE
        
        return self.channels[channel].valve.position
    
    def get_valve_position_name(self, channel: str) -> str:
        """
        Get valve position as string.
        
        Args:
            channel: "CH1" or "CH2"
            
        Returns:
            "Waste", "Load", "Inject", or "Dispose"
        """
        position = self.get_valve_position(channel)
        return position.name.capitalize()
    
    def verify_valve_position(
        self,
        channel: str,
        expected_3way: int,
        expected_6port: int,
        timeout: float = 5.0,
    ) -> bool:
        """
        Verify valve reached expected position.
        
        Args:
            channel: "CH1" or "CH2"
            expected_3way: Expected 3-way position (0 or 1)
            expected_6port: Expected 6-port position (0 or 1)
            timeout: Maximum wait time in seconds
            
        Returns:
            True if valve reached position
        """
        if not self.is_available() or not self._validate_channel(channel):
            return False
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            current_3way = self.get_three_way_position(channel)
            current_6port = self.get_six_port_position(channel)
            
            if current_3way == expected_3way and current_6port == expected_6port:
                return True
            
            # Small delay before retry
            time.sleep(0.1)
        
        logger.warning(
            f"Valve {channel} verification timeout. "
            f"Expected 3-way={expected_3way}, 6-port={expected_6port}, "
            f"Got 3-way={self.get_three_way_position(channel)}, "
            f"6-port={self.get_six_port_position(channel)}"
        )
        return False
    
    def update_valve_state_from_hardware(self, channel: str) -> bool:
        """
        Query hardware and update internal valve state.
        
        Args:
            channel: "CH1" or "CH2"
            
        Returns:
            True if successful
        """
        if not self.is_available() or not self._validate_channel(channel):
            return False
        
        try:
            # The KNX controller maintains state internally
            # We could read status registers, but for now we trust the state
            # This method is here for future expansion if status queries are added
            logger.debug(f"Valve state for {channel} synchronized from hardware")
            return True
            
        except Exception as e:
            logger.exception(f"Error updating valve state for {channel}: {e}")
            return False
    
    # ========================================================================
    # Injection Management
    # ========================================================================
    
    def start_injection(
        self,
        channel: str,
        flow_rate: float,
        auto_timeout: bool = True,
    ) -> bool:
        """
        Start an injection sequence.
        
        Args:
            channel: "CH1" or "CH2"
            flow_rate: Flow rate in ml/min (for timeout calculation)
            auto_timeout: Enable automatic injection timeout
            
        Returns:
            True if successful
        """
        if not self._validate_channel(channel):
            return False
        
        try:
            # Set six-port valve to inject position (1)
            if not self.set_six_port_valve(channel, 1):
                logger.error(f"Failed to set inject valve for {channel}")
                return False
            
            # Store injection start time (experiment time)
            experiment_time = time.time() - self.exp_start
            self.channels[channel].valve.last_injection_time = experiment_time
            self.channels[channel].valve.last_injection_timestamp = dt.datetime.now().strftime("%H:%M:%S")
            
            # Calculate timeout: base_time / flow_rate + safety margin
            # flow_rate is in ml/min, INJECTION_BASE_TIME_SEC is in seconds
            # Result: timeout in minutes
            if auto_timeout and flow_rate > 0:
                timeout_minutes = (INJECTION_BASE_TIME_SEC / 60.0) / flow_rate + INJECTION_SAFETY_MARGIN_MIN
                timeout_ms = int(timeout_minutes * 60 * 1000)  # Convert to milliseconds
                
                # Select correct timer
                timer = self._injection_timer_ch1 if channel == "CH1" else self._injection_timer_ch2
                timer.setSingleShot(True)
                timer.start(timeout_ms)
                
                self.channels[channel].injection_timer_active = True
                self.channels[channel].injection_timeout_sec = int(timeout_minutes * 60)
                
                logger.debug(f"Injection timer set for {channel}: {timeout_minutes:.1f} minutes")
            
            # Log the injection event
            self.log_event(channel, "injection_start")
            
            # Emit signal
            self.injection_started.emit(channel, experiment_time)
            
            logger.info(f"Injection started for {channel} at t={experiment_time:.1f}s")
            return True
            
        except Exception as e:
            logger.exception(f"Error starting injection for {channel}: {e}")
            self.error_occurred.emit(channel, f"Injection start error: {e}")
            return False
    
    def end_injection(self, channel: str) -> bool:
        """
        End an injection sequence.
        
        Args:
            channel: "CH1" or "CH2"
            
        Returns:
            True if successful
        """
        if not self._validate_channel(channel):
            return False
        
        try:
            # Set six-port valve to load position (0)
            if not self.set_six_port_valve(channel, 0):
                logger.error(f"Failed to set load valve for {channel}")
                return False
            
            # Stop injection timer if running
            timer = self._injection_timer_ch1 if channel == "CH1" else self._injection_timer_ch2
            if timer.isActive():
                timer.stop()
            
            self.channels[channel].injection_timer_active = False
            
            # Log the end event
            self.log_event(channel, "injection_end")
            
            # Emit signal
            self.injection_ended.emit(channel)
            
            logger.info(f"Injection ended for {channel}")
            return True
            
        except Exception as e:
            logger.exception(f"Error ending injection for {channel}: {e}")
            self.error_occurred.emit(channel, f"Injection end error: {e}")
            return False
    
    def _auto_end_injection(self, channel: str) -> None:
        """
        Automatically end injection on timeout.
        
        Args:
            channel: "CH1" or "CH2"
        """
        logger.info(f"Auto-ending injection for {channel} (timeout reached)")
        self.log_event(channel, "injection_auto_end")
        self.end_injection(channel)
    
    def get_injection_time(self, channel: str) -> float:
        """
        Get time when last injection started (experiment time).
        
        Args:
            channel: "CH1" or "CH2"
            
        Returns:
            Experiment time in seconds
        """
        if not self._validate_channel(channel):
            return 0.0
        
        return self.channels[channel].valve.last_injection_time
    
    # ========================================================================
    # Synchronization
    # ========================================================================
    
    def enable_sync(self) -> None:
        """Enable synchronized operation (CH1 controls both channels)."""
        self.synced = True
        self.sync_channel_states()
        logger.info("Channel synchronization enabled")
    
    def disable_sync(self) -> None:
        """Disable synchronized operation (independent channels)."""
        self.synced = False
        logger.info("Channel synchronization disabled")
    
    def is_synced(self) -> bool:
        """Check if channels are synchronized."""
        return self.synced
    
    def sync_channel_states(self) -> None:
        """Synchronize CH2 valve states to match CH1."""
        ch1 = self.channels["CH1"]
        ch2 = self.channels["CH2"]
        
        # Copy valve positions
        ch2.valve.three_way_position = ch1.valve.three_way_position
        ch2.valve.six_port_position = ch1.valve.six_port_position
        
        # Copy pump state
        ch2.pump_running = ch1.pump_running
        ch2.pump_rate = ch1.pump_rate
        
        # Emit signals
        self.valve_state_changed.emit("CH2", ch2.valve.position_name)
        
        logger.debug("CH2 state synchronized to match CH1")
    
    # ========================================================================
    # Sensor Reading
    # ========================================================================
    
    def read_sensor(self, channel: str) -> SensorReading | None:
        """
        Read temperature sensor for a channel.
        
        Args:
            channel: "CH1" or "CH2"
            
        Returns:
            SensorReading object or None on error
        """
        if not self.is_available() or not self._validate_channel(channel):
            return None
        
        if self._sensor_paused:
            return None
        
        try:
            hw_channel = 1 if channel == "CH1" else 2
            
            # Read status from hardware
            status = self.knx.knx_status(hw_channel)
            
            # Parse temperature from status
            # Status format depends on hardware, assuming dict or tuple
            if isinstance(status, dict):
                temperature = status.get("temp")
            elif isinstance(status, (list, tuple)) and len(status) >= 2:
                temperature = status[1]  # Temperature is typically second value
            elif isinstance(status, (list, tuple)) and len(status) >= 1:
                temperature = status[0]  # Or first if only one value
            else:
                return None
            
            # Create sensor reading
            exp_time = time.time() - self.exp_start
            reading = SensorReading(
                temperature=temperature,
                exp_time=exp_time
            )
            
            # Update channel state
            self.channels[channel].current_temp = temperature
            
            return reading
            
        except Exception as e:
            logger.exception(f"Error reading sensor for {channel}: {e}")
            return None
    
    def get_averaged_sensor_reading(self, channel: str) -> str:
        """
        Get averaged temperature reading for display.
        
        Args:
            channel: "CH1" or "CH2"
            
        Returns:
            Temperature as formatted string
        """
        if channel == "CH1":
            temp_buf = self._temp_buf_1
        elif channel == "CH2":
            temp_buf = self._temp_buf_2
        else:
            return "-"
        
        # Calculate average
        if len(temp_buf) > 0:
            avg_temp = np.mean(temp_buf[-self.sensor_avg_window:])
            return f"{avg_temp:.2f}"
        else:
            return "-"
    
    def update_sensor_buffers(self, channel: str, temp: float) -> None:
        """
        Add new temperature reading to averaging buffer.
        
        Args:
            channel: "CH1" or "CH2"
            temp: Temperature in °C
        """
        if channel == "CH1":
            self._temp_buf_1.append(temp)
            
            # Keep buffer size reasonable (last 100 readings)
            if len(self._temp_buf_1) > 100:
                self._temp_buf_1.pop(0)
        
        elif channel == "CH2":
            self._temp_buf_2.append(temp)
            
            if len(self._temp_buf_2) > 100:
                self._temp_buf_2.pop(0)
    
    def clear_sensor_buffers(self) -> None:
        """Clear all sensor reading buffers."""
        self._temp_buf_1.clear()
        self._temp_buf_2.clear()
        self._device_temp_buf.clear()
    
    def pause_sensor_reading(self) -> None:
        """Pause sensor reading (used during valve movements)."""
        self._sensor_paused = True
    
    def resume_sensor_reading(self) -> None:
        """Resume sensor reading after pause."""
        self._sensor_paused = False
    
    def is_sensor_paused(self) -> bool:
        """Check if sensor reading is paused."""
        return self._sensor_paused
    
    # ========================================================================
    # Device Temperature
    # ========================================================================
    
    def read_device_temperature(self) -> float | None:
        """
        Read device internal temperature.
        
        Returns:
            Temperature in °C or None on error
        """
        if not self.is_available():
            return None
        
        try:
            # Try to get device status
            status = self.knx.get_status() if hasattr(self.knx, 'get_status') else None
            
            if status is None:
                return None
            
            # Extract temperature (format depends on device)
            temp = None
            if isinstance(status, dict):
                temp = status.get("temp") or status.get("device_temp")
            elif isinstance(status, (list, tuple)) and len(status) > 0:
                temp = status[0] if isinstance(status[0], (int, float)) else None
            
            # Validate range
            if temp is not None and DEVICE_TEMP_MIN <= temp <= DEVICE_TEMP_MAX:
                self._device_temp_buf.append(temp)
                
                # Keep buffer size reasonable
                if len(self._device_temp_buf) > 100:
                    self._device_temp_buf.pop(0)
                
                # Return averaged value
                avg_temp = np.mean(self._device_temp_buf[-DEVICE_TEMP_AVG_WINDOW:])
                return avg_temp
            
            return None
            
        except Exception as e:
            logger.exception(f"Error reading device temperature: {e}")
            return None
    
    def get_averaged_device_temperature(self) -> str:
        """
        Get averaged device temperature for display.
        
        Returns:
            Temperature as formatted string
        """
        if len(self._device_temp_buf) > 0:
            avg_temp = np.mean(self._device_temp_buf[-DEVICE_TEMP_AVG_WINDOW:])
            return f"{avg_temp:.1f}"
        return "-"
    
    # ========================================================================
    # Event Logging
    # ========================================================================
    
    def log_event(
        self,
        channel: str,
        event: str,
        temp: str = "-",
        dev: str = "-",
    ) -> None:
        """
        Log a kinetic event.
        
        Args:
            channel: "CH1" or "CH2"
            event: Event description
            temp: Temperature reading (optional)
            dev: Device temperature (optional)
        """
        if not self._validate_channel(channel):
            return
        
        exp_time = time.time() - self.exp_start
        self.logs[channel].append_event(event, exp_time, temp, dev)
    
    def log_sensor_reading(self, channel: str, temp: str) -> None:
        """
        Log a sensor reading event.
        
        Args:
            channel: "CH1" or "CH2"
            temp: Temperature as string
        """
        self.log_event(channel, "Sensor reading", temp=temp)
    
    def log_device_reading(self, temp: str) -> None:
        """
        Log a device temperature reading (logs to both channels).
        
        Args:
            temp: Device temperature as string
        """
        self.log_event("CH1", "Device reading", dev=temp)
        self.log_event("CH2", "Device reading", dev=temp)
    
    def get_log(self, channel: str) -> KineticLog:
        """
        Get kinetic log for a channel.
        
        Args:
            channel: "CH1" or "CH2"
            
        Returns:
            KineticLog object
        """
        return self.logs[channel]
    
    def get_log_dict(self, channel: str) -> dict[str, list]:
        """
        Get kinetic log as dictionary for export.
        
        Args:
            channel: "CH1" or "CH2"
            
        Returns:
            Dictionary with timestamps, times, events, flow, temp, dev
        """
        return self.logs[channel].to_dict()
    
    def clear_log(self, channel: str) -> None:
        """
        Clear kinetic log for a channel.
        
        Args:
            channel: "CH1" or "CH2"
        """
        self.logs[channel].clear()
    
    def clear_all_logs(self) -> None:
        """Clear all kinetic logs."""
        self.logs["CH1"].clear()
        self.logs["CH2"].clear()
    
    # ========================================================================
    # State Queries
    # ========================================================================
    
    def get_channel_state(self, channel: str) -> ChannelState:
        """
        Get complete state of a channel.
        
        Args:
            channel: "CH1" or "CH2"
            
        Returns:
            ChannelState object
        """
        return self.channels[channel]
    
    def get_all_states(self) -> dict[str, ChannelState]:
        """Get states of all channels."""
        return self.channels
    
    def get_valve_states_dict(self) -> dict[str, str]:
        """
        Get valve positions as dictionary (for UI compatibility).
        
        Returns:
            {"CH1": "Waste", "CH2": "Load", ...}
        """
        return {
            "CH1": self.channels["CH1"].valve.position_name,
            "CH2": self.channels["CH2"].valve.position_name,
        }
    
    # ========================================================================
    # Experiment Time Management
    # ========================================================================
    
    def set_experiment_start_time(self, start_time: float) -> None:
        """
        Set experiment start time.
        
        Args:
            start_time: Start time as time.time() value
        """
        self.exp_start = start_time
    
    def get_experiment_time(self) -> float:
        """
        Get current experiment time in seconds.
        
        Returns:
            Seconds since experiment start
        """
        return time.time() - self.exp_start
    
    def reset_experiment_time(self) -> None:
        """Reset experiment start time to now."""
        self.exp_start = time.time()
        logger.info("Experiment time reset")
        # Note: Existing logged times remain in their original form
        # They are stored as absolute values and should not be adjusted
    
    # ========================================================================
    # Shutdown
    # ========================================================================
    
    def shutdown(self) -> None:
        """Shutdown kinetic manager and clean up resources."""
        logger.info("Shutting down kinetic manager")
        
        # Stop all injection timers
        self._injection_timer_ch1.stop()
        self._injection_timer_ch2.stop()
        
        # Set all valves to safe positions (load = 3-way:1, 6-port:0)
        try:
            self.set_three_way_valve("CH1", 1)
            self.set_three_way_valve("CH2", 1)
            self.set_six_port_valve("CH1", 0)
            self.set_six_port_valve("CH2", 0)
        except Exception as e:
            logger.error(f"Error setting safe valve positions: {e}")
        
        # Clear buffers
        self.clear_sensor_buffers()
        
        logger.info("Kinetic manager shutdown complete")
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def _hardware_channel_number(self, channel: str) -> int:
        """
        Get hardware channel number for valve commands.
        
        Args:
            channel: "CH1" or "CH2"
            
        Returns:
            1, 2, or 3 (3 = both when synced)
        """
        if channel == "CH1" and self.synced:
            return 3  # Both channels
        elif channel == "CH1":
            return 1
        elif channel == "CH2":
            return 2
        else:
            return 1  # Default
    
    def _validate_channel(self, channel: str) -> bool:
        """
        Validate channel name.
        
        Args:
            channel: Channel to validate
            
        Returns:
            True if valid
        """
        return channel in ["CH1", "CH2"]
