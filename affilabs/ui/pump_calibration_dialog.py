"""Pump Calibration Dialog - Advanced settings for internal pump speed matching.

This dialog allows users to adjust correction factors for KC1 and KC2 pumps
to compensate for manufacturing variations and ensure matched flow rates.
"""

from PySide6.QtWidgets import QDialog, QMessageBox
from affilabs.ui.ui_pump_calibration_dialog import Ui_PumpCalibrationDialog
from affilabs.utils.logger import logger


class PumpCalibrationDialog(QDialog):
    """Dialog for calibrating internal pump speeds.
    
    Provides UI to adjust pump correction factors that compensate for
    mechanical variations between the two peristaltic pumps.
    """
    
    def __init__(self, controller=None, parent=None):
        """Initialize the pump calibration dialog.
        
        Args:
            controller: Controller instance with get/set_pump_corrections methods
            parent: Parent widget
        """
        super().__init__(parent)
        self.controller = controller
        
        # Setup UI
        self.ui = Ui_PumpCalibrationDialog()
        self.ui.setupUi(self)
        
        # Connect signals
        self._connect_signals()
        
        # Load current values
        self._load_current_corrections()
        
    def _connect_signals(self):
        """Connect button signals to handlers."""
        self.ui.pump1_reset_btn.clicked.connect(self._reset_pump1)
        self.ui.pump2_reset_btn.clicked.connect(self._reset_pump2)
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Apply).clicked.connect(self._apply_corrections)
        
    def _load_current_corrections(self):
        """Load current pump corrections from controller."""
        if not self.controller:
            logger.warning("No controller available for pump calibration")
            return
            
        try:
            corrections = self.controller.get_pump_corrections()
            if corrections and len(corrections) >= 2:
                self.ui.pump1_spinbox.setValue(corrections[0])
                self.ui.pump2_spinbox.setValue(corrections[1])
                logger.info(f"Loaded pump corrections: KC1={corrections[0]:.3f}, KC2={corrections[1]:.3f}")
            else:
                logger.info("No pump corrections available, using defaults (1.0, 1.0)")
                self.ui.pump1_spinbox.setValue(1.000)
                self.ui.pump2_spinbox.setValue(1.000)
        except Exception as e:
            logger.error(f"Error loading pump corrections: {e}")
            QMessageBox.warning(
                self,
                "Load Error",
                f"Could not load pump corrections:\n{e}\n\nUsing default values."
            )
            
    def _reset_pump1(self):
        """Reset KC1 correction to 1.0."""
        self.ui.pump1_spinbox.setValue(1.000)
        logger.debug("KC1 correction reset to 1.000")
        
    def _reset_pump2(self):
        """Reset KC2 correction to 1.0."""
        self.ui.pump2_spinbox.setValue(1.000)
        logger.debug("KC2 correction reset to 1.000")
        
    def _apply_corrections(self):
        """Apply current corrections to controller."""
        if not self.controller:
            QMessageBox.warning(
                self,
                "No Controller",
                "Controller not connected. Connect to P4PRO/EZSPR to apply corrections."
            )
            return
            
        kc1_correction = self.ui.pump1_spinbox.value()
        kc2_correction = self.ui.pump2_spinbox.value()
        
        try:
            success = self.controller.set_pump_corrections(kc1_correction, kc2_correction)
            if success:
                logger.info(f"✓ Pump corrections applied: KC1={kc1_correction:.3f}, KC2={kc2_correction:.3f}")
                QMessageBox.information(
                    self,
                    "Success",
                    f"Pump corrections applied successfully:\n\n"
                    f"KC1: {kc1_correction:.3f}\n"
                    f"KC2: {kc2_correction:.3f}"
                )
            else:
                logger.error("Failed to apply pump corrections")
                QMessageBox.warning(
                    self,
                    "Apply Failed",
                    "Could not apply pump corrections.\n\n"
                    "Check that controller firmware supports calibration (V1.4+)."
                )
        except Exception as e:
            logger.error(f"Error applying pump corrections: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Error applying pump corrections:\n{e}"
            )
            
    def accept(self):
        """Handle OK button - apply and close."""
        self._apply_corrections()
        super().accept()
        
    def get_corrections(self):
        """Get current correction values from dialog.
        
        Returns:
            tuple: (kc1_correction, kc2_correction)
        """
        return (self.ui.pump1_spinbox.value(), self.ui.pump2_spinbox.value())
