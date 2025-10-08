"""
UI State Manager Module

Centralized management of UI state including widget enabling/disabling,
status messages, and widget text updates.

Author: Extracted from main.py during Phase 11 refactoring
Date: October 8, 2025
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Optional

from utils.logger import logger

if TYPE_CHECKING:
    from widgets.mainwindow import MainWindow


class UIStateManager:
    """
    Manages UI state and widget operations across the application.
    
    Centralizes:
    - Status message updates
    - Widget enable/disable operations
    - Text field updates
    - Control state management during operations
    """
    
    def __init__(self, main_window: MainWindow):
        """
        Initialize the UI State Manager.
        
        Args:
            main_window: Main window instance for UI access
        """
        self.main_window = main_window
    
    # ========================================================================
    # STATUS MANAGEMENT
    # ========================================================================
    
    def set_status_text(self, text: str) -> None:
        """
        Update the main status bar text.
        
        Args:
            text: Status message to display
        """
        try:
            self.main_window.ui.status.setText(text)
            logger.debug(f"Status updated: {text}")
        except Exception as e:
            logger.exception(f"Error setting status text: {e}")
    
    def set_device_display(self, text: str) -> None:
        """
        Update the device display text.
        
        Args:
            text: Device information to display
        """
        try:
            self.main_window.ui.device.setText(text)
        except Exception as e:
            logger.exception(f"Error setting device display: {e}")
    
    # ========================================================================
    # CALIBRATION STATE MANAGEMENT
    # ========================================================================
    
    def set_calibration_state(self, calibrating: bool) -> None:
        """
        Set UI state for calibration process.
        
        Args:
            calibrating: True if calibration is starting, False if ending
        """
        try:
            if calibrating:
                self.set_status_text("Calibrating")
                self._disable_controls_for_calibration()
            else:
                self.set_status_text("Connected")
                self._enable_controls_after_calibration()
                
        except Exception as e:
            logger.exception(f"Error setting calibration state: {e}")
    
    def _disable_controls_for_calibration(self) -> None:
        """Disable controls during calibration."""
        try:
            # Disable sensorgram controls
            self.main_window.sensorgram.enable_controls(data_ready=False)
            
            # Disable spectroscopy controls
            self.main_window.spectroscopy.enable_controls(False)
            
            # Disable device widget commands if available
            if getattr(self.main_window.sidebar, "device_widget", None) is not None:
                self.main_window.sidebar.device_widget.allow_commands(False)
                
        except Exception as e:
            logger.exception(f"Error disabling calibration controls: {e}")
    
    def _enable_controls_after_calibration(self) -> None:
        """Enable controls after calibration."""
        try:
            # Enable spectroscopy controls
            self.main_window.spectroscopy.enable_controls(True)
            
            # Enable device widget commands if available
            if getattr(self.main_window.sidebar, "device_widget", None) is not None:
                self.main_window.sidebar.device_widget.allow_commands(True)
                
            # Enable advanced settings button
            self.main_window.ui.adv_btn.setEnabled(True)
            
        except Exception as e:
            logger.exception(f"Error enabling calibration controls: {e}")
    
    # ========================================================================
    # REFERENCE SPECTRUM STATE MANAGEMENT
    # ========================================================================
    
    def set_new_reference_state(self, starting: bool) -> None:
        """
        Set UI state for new reference spectrum process.
        
        Args:
            starting: True if starting new reference, False if ending
        """
        try:
            if starting:
                self.set_status_text("New reference ...")
                self._disable_controls_for_reference()
            else:
                self.set_status_text("Connected")
                self._enable_controls_after_reference()
                
        except Exception as e:
            logger.exception(f"Error setting new reference state: {e}")
    
    def _disable_controls_for_reference(self) -> None:
        """Disable controls during new reference."""
        try:
            # Disable spectroscopy controls
            self.main_window.spectroscopy.ui.controls.setEnabled(False)
            
            # Disable device widget commands if available
            if getattr(self.main_window.sidebar, "device_widget", None) is not None:
                self.main_window.sidebar.device_widget.allow_commands(state=False)
                
        except Exception as e:
            logger.exception(f"Error disabling reference controls: {e}")
    
    def _enable_controls_after_reference(self) -> None:
        """Enable controls after new reference."""
        try:
            # Enable spectroscopy controls
            self.main_window.spectroscopy.ui.controls.setEnabled(True)
            
            # Enable device widget commands if available
            if getattr(self.main_window.sidebar, "device_widget", None) is not None:
                self.main_window.sidebar.device_widget.allow_commands(state=True)
                
        except Exception as e:
            logger.exception(f"Error enabling reference controls: {e}")
    
    # ========================================================================
    # CONNECTION STATE MANAGEMENT
    # ========================================================================
    
    def set_connection_error_state(self) -> None:
        """Set UI state for connection errors."""
        try:
            self.set_status_text("Device Connection Error")
        except Exception as e:
            logger.exception(f"Error setting connection error state: {e}")
    
    def set_connection_state(self, connected: bool) -> None:
        """
        Set UI state based on connection status.
        
        Args:
            connected: True if connected, False if disconnected
        """
        try:
            if connected:
                self.set_status_text("Connected")
            else:
                self.set_status_text("Connection Error")
        except Exception as e:
            logger.exception(f"Error setting connection state: {e}")
    
    def set_scanning_state(self) -> None:
        """Set UI state when scanning for devices."""
        try:
            self.set_status_text("Scanning for devices...")
        except Exception as e:
            logger.exception(f"Error setting scanning state: {e}")
    
    def set_initialization_error_state(self) -> None:
        """Set UI state for device initialization errors."""
        try:
            self.set_status_text("Device initialization error")
        except Exception as e:
            logger.exception(f"Error setting initialization error state: {e}")
    
    # ========================================================================
    # ADVANCED SETTINGS MANAGEMENT
    # ========================================================================
    
    def set_advanced_settings_enabled(self, enabled: bool) -> None:
        """
        Enable or disable advanced settings button.
        
        Args:
            enabled: True to enable, False to disable
        """
        try:
            self.main_window.ui.adv_btn.setEnabled(enabled)
        except Exception as e:
            logger.exception(f"Error setting advanced settings state: {e}")
    
    # ========================================================================
    # KINETIC WIDGET UPDATES
    # ========================================================================
    
    def update_inject_times(self, exp_time: float, channels: list[str]) -> None:
        """
        Update injection time displays in kinetic widget.
        
        Args:
            exp_time: Experiment time to display
            channels: List of channels to update ("CH1", "CH2")
        """
        try:
            kinetic_widget = getattr(self.main_window.sidebar, "kinetic_widget", None)
            if kinetic_widget is not None:
                if "CH1" in channels:
                    kinetic_widget.ui.inject_time_ch1.setText(f"{exp_time:.2f}")
                if "CH2" in channels:
                    kinetic_widget.ui.inject_time_ch2.setText(f"{exp_time:.2f}")
        except Exception as e:
            logger.exception(f"Error updating inject times: {e}")
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def get_status_callback(self) -> Callable[[str], None]:
        """
        Get a callback function for status updates.
        
        Returns:
            Callable: Function that takes status text and updates UI
        """
        return lambda text: self.set_status_text(text)
    
    def get_device_callback(self) -> Callable[[str], None]:
        """
        Get a callback function for device display updates.
        
        Returns:
            Callable: Function that takes device text and updates UI
        """
        return lambda text: self.set_device_display(text)
    
    def cleanup(self) -> None:
        """Clean up UI state manager resources."""
        logger.debug("UIStateManager cleanup completed")