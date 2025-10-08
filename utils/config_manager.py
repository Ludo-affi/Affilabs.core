"""Configuration Management for Affinite Instruments SPR system.

This module provides centralized configuration management for all system settings,
calibration data, device configurations, and application state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np

from settings import CH_LIST, MIN_INTEGRATION
from utils.logger import logger


@dataclass
class DeviceConfiguration:
    """Device hardware configuration."""
    ctrl: str = ""
    knx: str = ""
    pump: Optional[str] = None
    usb: str = ""
    
    def to_dict(self) -> Dict[str, Optional[str]]:
        """Convert to dictionary format."""
        return asdict(self)
    
    def is_valid(self) -> bool:
        """Check if configuration has required devices."""
        return bool(self.ctrl or self.knx)


@dataclass
class CalibrationConfiguration:
    """Calibration settings and data."""
    integration: int = MIN_INTEGRATION
    ref_intensity: Dict[str, int] = field(default_factory=lambda: {ch: 0 for ch in CH_LIST})
    pol_intensity: Dict[str, int] = field(default_factory=lambda: {ch: 0 for ch in CH_LIST})
    wave_data: Optional[np.ndarray] = None
    dark_noise: Optional[np.ndarray] = None
    fourier_weights: Optional[np.ndarray] = None
    
    def has_calibration_data(self) -> bool:
        """Check if calibration data is available."""
        return (
            self.wave_data is not None 
            and self.dark_noise is not None 
            and any(intensity > 0 for intensity in self.ref_intensity.values())
        )
    
    def reset(self) -> None:
        """Reset all calibration data."""
        self.integration = MIN_INTEGRATION
        self.ref_intensity = {ch: 0 for ch in CH_LIST}
        self.pol_intensity = {ch: 0 for ch in CH_LIST}
        self.wave_data = None
        self.dark_noise = None
        self.fourier_weights = None


@dataclass
class TemperatureConfiguration:
    """Temperature logging configuration."""
    readings: List[float] = field(default_factory=list)
    times: List[float] = field(default_factory=list)
    exp: List[float] = field(default_factory=list)
    
    def clear(self) -> None:
        """Clear all temperature logs."""
        self.readings.clear()
        self.times.clear()
        self.exp.clear()
    
    def add_reading(self, temperature: float, timestamp: float, exp_time: float = 0.0) -> None:
        """Add a temperature reading."""
        self.readings.append(temperature)
        self.times.append(timestamp)
        self.exp.append(exp_time)
    
    def to_dict(self) -> Dict[str, List[float]]:
        """Convert to dictionary format."""
        return {
            "readings": self.readings,
            "times": self.times,
            "exp": self.exp
        }


@dataclass
class KineticConfiguration:
    """Kinetic system configuration."""
    flow_rate: int = 100  # μL/min
    recording: bool = False
    synced: bool = False
    valve_states: Dict[str, Any] = field(default_factory=dict)
    pump_states: Dict[str, Any] = field(default_factory=dict)
    
    def reset_states(self) -> None:
        """Reset valve and pump states."""
        self.valve_states.clear()
        self.pump_states.clear()


@dataclass
class UIConfiguration:
    """User interface configuration."""
    filt_on: bool = False
    auto_scale: bool = True
    plot_range: Optional[Dict[str, float]] = None
    show_filtered: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return asdict(self)


class ConfigurationManager:
    """Centralized configuration manager for the SPR system.
    
    This class manages all configuration data including device settings,
    calibration data, temperature logs, kinetic settings, and UI preferences.
    """

    def __init__(self) -> None:
        """Initialize configuration manager with default settings."""
        # Core configuration sections
        self.device = DeviceConfiguration()
        self.calibration = CalibrationConfiguration()
        self.temperature = TemperatureConfiguration()
        self.kinetic = KineticConfiguration()
        self.ui = UIConfiguration()
        
        # Runtime state
        self._is_initialized = False
        
        logger.debug("ConfigurationManager initialized")

    def initialize_defaults(self) -> None:
        """Initialize all configurations with default values."""
        if self._is_initialized:
            return
            
        # Device configuration defaults
        self.device = DeviceConfiguration()
        
        # Calibration defaults
        self.calibration = CalibrationConfiguration()
        
        # Temperature logging defaults
        self.temperature = TemperatureConfiguration()
        
        # Kinetic system defaults
        self.kinetic = KineticConfiguration()
        
        # UI defaults
        self.ui = UIConfiguration()
        
        self._is_initialized = True
        logger.info("Configuration manager initialized with defaults")

    def update_device_config(self, ctrl: str = "", knx: str = "", 
                           pump: Optional[str] = None, usb: str = "") -> None:
        """Update device configuration.
        
        Args:
            ctrl: SPR controller device name
            knx: Kinetic controller device name  
            pump: Pump controller device name
            usb: USB spectrometer device name
        """
        self.device.ctrl = ctrl
        self.device.knx = knx
        self.device.pump = pump
        self.device.usb = usb
        logger.debug(f"Device config updated: {self.device.to_dict()}")

    def update_calibration_from_state(self, calibrator_state: Any) -> None:
        """Update calibration configuration from calibrator state.
        
        Args:
            calibrator_state: Calibrator state object with calibration data
        """
        if hasattr(calibrator_state, 'wave_data'):
            self.calibration.wave_data = calibrator_state.wave_data
        if hasattr(calibrator_state, 'integration'):
            self.calibration.integration = calibrator_state.integration
        if hasattr(calibrator_state, 'ref_intensity'):
            self.calibration.ref_intensity = calibrator_state.ref_intensity.copy()
        if hasattr(calibrator_state, 'pol_intensity'):
            self.calibration.pol_intensity = calibrator_state.pol_intensity.copy()
        if hasattr(calibrator_state, 'dark_noise'):
            self.calibration.dark_noise = calibrator_state.dark_noise
        if hasattr(calibrator_state, 'fourier_weights'):
            self.calibration.fourier_weights = calibrator_state.fourier_weights
            
        logger.debug("Calibration config updated from calibrator state")

    def get_device_config_dict(self) -> Dict[str, Optional[str]]:
        """Get device configuration as dictionary (for backward compatibility)."""
        return self.device.to_dict()

    def get_calibration_params(self) -> Dict[str, Any]:
        """Get calibration parameters for manager initialization."""
        return {
            "integration": self.calibration.integration,
            "ref_intensity": self.calibration.ref_intensity,
            "pol_intensity": self.calibration.pol_intensity,
            "wave_data": self.calibration.wave_data,
            "dark_noise": self.calibration.dark_noise,
            "fourier_weights": self.calibration.fourier_weights,
        }

    def get_temp_log_dict(self) -> Dict[str, List[float]]:
        """Get temperature log as dictionary (for backward compatibility)."""
        return self.temperature.to_dict()

    def add_temperature_reading(self, temperature: float, timestamp: float, exp_time: float = 0.0) -> None:
        """Add a temperature reading to the log."""
        self.temperature.add_reading(temperature, timestamp, exp_time)

    def clear_temperature_log(self) -> None:
        """Clear all temperature readings."""
        self.temperature.clear()

    def set_flow_rate(self, rate: int) -> None:
        """Set kinetic flow rate."""
        self.kinetic.flow_rate = rate
        logger.debug(f"Flow rate set to {rate} μL/min")

    def set_recording_state(self, recording: bool) -> None:
        """Set recording state."""
        self.kinetic.recording = recording
        logger.debug(f"Recording state set to {recording}")

    def set_sync_state(self, synced: bool) -> None:
        """Set synchronization state."""
        self.kinetic.synced = synced
        logger.debug(f"Sync state set to {synced}")

    def update_valve_state(self, valve_states: Dict[str, Any]) -> None:
        """Update valve states."""
        self.kinetic.valve_states.update(valve_states)

    def update_pump_state(self, pump_states: Dict[str, Any]) -> None:
        """Update pump states."""
        self.kinetic.pump_states.update(pump_states)

    def set_filter_state(self, enabled: bool) -> None:
        """Set data filtering state."""
        self.ui.filt_on = enabled
        logger.debug(f"Data filtering set to {enabled}")

    def reset_all_configurations(self) -> None:
        """Reset all configurations to defaults."""
        self.device = DeviceConfiguration()
        self.calibration.reset()
        self.temperature.clear()
        self.kinetic.reset_states()
        self.ui = UIConfiguration()
        logger.info("All configurations reset to defaults")

    def save_configuration(self, file_path: Path) -> bool:
        """Save configuration to JSON file.
        
        Args:
            file_path: Path to save configuration file
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            config_data = {
                "device": self.device.to_dict(),
                "calibration": {
                    "integration": self.calibration.integration,
                    "ref_intensity": self.calibration.ref_intensity,
                    "pol_intensity": self.calibration.pol_intensity,
                    # Note: numpy arrays would need special handling for JSON
                },
                "kinetic": {
                    "flow_rate": self.kinetic.flow_rate,
                    "recording": self.kinetic.recording,
                    "synced": self.kinetic.synced,
                },
                "ui": self.ui.to_dict(),
            }
            
            with open(file_path, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            logger.info(f"Configuration saved to {file_path}")
            return True
            
        except Exception as e:
            logger.exception(f"Error saving configuration: {e}")
            return False

    def load_configuration(self, file_path: Path) -> bool:
        """Load configuration from JSON file.
        
        Args:
            file_path: Path to configuration file
            
        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            with open(file_path, 'r') as f:
                config_data = json.load(f)
            
            # Load device configuration
            if "device" in config_data:
                device_data = config_data["device"]
                self.device = DeviceConfiguration(**device_data)
            
            # Load calibration configuration
            if "calibration" in config_data:
                cal_data = config_data["calibration"]
                self.calibration.integration = cal_data.get("integration", MIN_INTEGRATION)
                self.calibration.ref_intensity = cal_data.get("ref_intensity", {ch: 0 for ch in CH_LIST})
                self.calibration.pol_intensity = cal_data.get("pol_intensity", {ch: 0 for ch in CH_LIST})
            
            # Load kinetic configuration
            if "kinetic" in config_data:
                kinetic_data = config_data["kinetic"]
                self.kinetic.flow_rate = kinetic_data.get("flow_rate", 100)
                self.kinetic.recording = kinetic_data.get("recording", False)
                self.kinetic.synced = kinetic_data.get("synced", False)
            
            # Load UI configuration
            if "ui" in config_data:
                ui_data = config_data["ui"]
                self.ui.filt_on = ui_data.get("filt_on", False)
                self.ui.auto_scale = ui_data.get("auto_scale", True)
            
            logger.info(f"Configuration loaded from {file_path}")
            return True
            
        except Exception as e:
            logger.exception(f"Error loading configuration: {e}")
            return False

    def get_configuration_summary(self) -> Dict[str, Any]:
        """Get a summary of current configuration state."""
        return {
            "device_valid": self.device.is_valid(),
            "has_calibration": self.calibration.has_calibration_data(),
            "temperature_readings": len(self.temperature.readings),
            "flow_rate": self.kinetic.flow_rate,
            "recording": self.kinetic.recording,
            "filtering_enabled": self.ui.filt_on,
        }