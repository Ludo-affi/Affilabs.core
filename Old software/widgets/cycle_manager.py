"""Cycle Type and Time Management

Handles cycle type/time logic, validation, and UI state management.
Extracted from datawindow.py to improve code organization and maintainability.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from widgets.ui_constants import CycleConfig

if TYPE_CHECKING:
    from PySide6.QtWidgets import QComboBox
    from widgets.graphs import SensorgramGraph


class CycleManager:
    """Manages cycle type and time interactions.
    
    Responsibilities:
    - Validate cycle type/time combinations
    - Handle UI state (enable/disable time dropdown)
    - Manage shaded region visibility
    - Extract cycle time values from UI
    - Provide defaults for cycle types
    """
    
    def __init__(
        self,
        cycle_type_dropdown: QComboBox,
        cycle_time_dropdown: QComboBox,
        sensorgram_graph: SensorgramGraph
    ):
        """Initialize cycle manager.
        
        Args:
            cycle_type_dropdown: The cycle type QComboBox
            cycle_time_dropdown: The cycle time QComboBox
            sensorgram_graph: The sensorgram graph (for shaded region)
        """
        self.cycle_type_dropdown = cycle_type_dropdown
        self.cycle_time_dropdown = cycle_time_dropdown
        self.sensorgram_graph = sensorgram_graph
        
        # Connect signals
        self.cycle_type_dropdown.currentTextChanged.connect(self._on_type_changed)
        self.cycle_time_dropdown.currentTextChanged.connect(self._on_time_changed)
    
    def _on_type_changed(self, cycle_type: str) -> None:
        """Handle cycle type changes.
        
        Args:
            cycle_type: The selected cycle type
        """
        if cycle_type == "Auto-read":
            # Auto-read: disable cycle time dropdown and hide shaded region
            self.cycle_time_dropdown.setEnabled(False)
            self.cycle_time_dropdown.setCurrentText("5 min")
            self.sensorgram_graph.hide_cycle_time_region()
            
        elif cycle_type == "Baseline":
            # Baseline: set to 5 min and disable, show shaded region
            self.cycle_time_dropdown.setCurrentText("5 min")
            self.cycle_time_dropdown.setEnabled(False)
            self.sensorgram_graph.show_cycle_time_region(5)
            
        elif cycle_type in ["Flow", "Static"]:
            # Flow/Static: enable user selection and show shaded region
            self.cycle_time_dropdown.setEnabled(True)
            cycle_time_minutes = self.get_current_time_minutes()
            if cycle_time_minutes is not None:
                self.sensorgram_graph.show_cycle_time_region(cycle_time_minutes)
    
    def _on_time_changed(self, time_text: str) -> None:
        """Handle cycle time changes.
        
        Args:
            time_text: The selected time text (e.g., "15 min")
        """
        cycle_type = self.cycle_type_dropdown.currentText()
        if cycle_type in ["Flow", "Static"]:
            cycle_time_minutes = self.parse_time_text(time_text)
            if cycle_time_minutes is not None:
                self.sensorgram_graph.show_cycle_time_region(cycle_time_minutes)
    
    def get_current_type(self) -> str:
        """Get currently selected cycle type.
        
        Returns:
            The cycle type string
        """
        return self.cycle_type_dropdown.currentText()
    
    def get_current_time_minutes(self) -> Optional[int]:
        """Get currently selected cycle time in minutes.
        
        Returns:
            Cycle time in minutes, or None for Auto-read
        """
        cycle_type = self.get_current_type()
        
        if cycle_type == "Auto-read":
            return None
        elif cycle_type == "Baseline":
            return 5
        else:
            # Flow or Static
            time_text = self.cycle_time_dropdown.currentText()
            return self.parse_time_text(time_text)
    
    @staticmethod
    def parse_time_text(time_text: str) -> Optional[int]:
        """Parse time text to extract minutes.
        
        Args:
            time_text: Text like "15 min"
            
        Returns:
            Time in minutes, or None if invalid
        """
        try:
            return int(time_text.split()[0])
        except (ValueError, IndexError):
            return None
    
    def set_cycle_info(self, cycle_type: str, cycle_time: Optional[int]) -> None:
        """Set cycle type and time from saved data.
        
        Args:
            cycle_type: The cycle type to set
            cycle_time: The cycle time in minutes (or None)
        """
        # Block signals during programmatic update
        self.cycle_type_dropdown.blockSignals(True)
        self.cycle_time_dropdown.blockSignals(True)
        
        try:
            # Set cycle type
            self.cycle_type_dropdown.setCurrentText(cycle_type)
            
            # Set cycle time
            if cycle_time is not None:
                self.cycle_time_dropdown.setCurrentText(f"{cycle_time} min")
            
            # Update UI state based on type
            if cycle_type == "Auto-read":
                self.cycle_time_dropdown.setEnabled(False)
            elif cycle_type == "Baseline":
                self.cycle_time_dropdown.setEnabled(False)
            elif cycle_type in ["Flow", "Static"]:
                self.cycle_time_dropdown.setEnabled(True)
                
        finally:
            # Restore signal connections
            self.cycle_type_dropdown.blockSignals(False)
            self.cycle_time_dropdown.blockSignals(False)
    
    def reset_to_default(self) -> None:
        """Reset to default cycle type (Auto-read)."""
        self.cycle_type_dropdown.setCurrentText("Auto-read")
        self.cycle_time_dropdown.setCurrentText("5 min")
        self.cycle_time_dropdown.setEnabled(False)
        self.sensorgram_graph.hide_cycle_time_region()
    
    @staticmethod
    def get_default_time(cycle_type: str) -> Optional[int]:
        """Get default cycle time for a given type.
        
        Args:
            cycle_type: The cycle type
            
        Returns:
            Default time in minutes, or None
        """
        return CycleConfig.get_default_time(cycle_type)
    
    @staticmethod
    def is_time_enabled(cycle_type: str) -> bool:
        """Check if time dropdown should be enabled.
        
        Args:
            cycle_type: The cycle type
            
        Returns:
            True if time dropdown should be enabled
        """
        return CycleConfig.is_time_enabled(cycle_type)
