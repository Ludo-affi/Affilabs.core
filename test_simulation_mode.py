"""Simulation Mode for Testing Queue Workflow Without Hardware

This script enables testing the complete cycle queue workflow without connected devices.

Features:
- Simulated SPR data generation
- Automatic cycle progression
- Real-time intelligence bar updates
- Cycle markers and completion
- Data recording to Cycle Data Table

Usage:
    python test_simulation_mode.py

The simulation will:
1. Auto-connect to simulated detector
2. Start simulated data acquisition
3. Allow you to build cycles and run queue
4. Generate realistic SPR curves during cycles
"""

import sys
import time
import numpy as np
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer

# Import main application
from main import Application
from affilabs.utils.logger import logger


class SimulatedDataGenerator:
    """Generate realistic SPR data for testing."""
    
    def __init__(self):
        self.time_offset = 0
        self.baseline = 1000  # RU
        self.noise_level = 2  # RU
        self.association_rate = 50  # RU/min
        self.dissociation_rate = -30  # RU/min
        self.current_phase = "baseline"
        self.phase_start_time = 0
        
    def get_data_point(self, elapsed_time):
        """Generate single SPR data point based on current phase.
        
        Args:
            elapsed_time: Time in seconds since start
            
        Returns:
            dict with SPR values for channels a, b, c, d
        """
        # Add realistic noise
        noise = np.random.normal(0, self.noise_level)
        
        # Calculate signal based on phase
        if self.current_phase == "baseline":
            signal = self.baseline
        elif self.current_phase == "association":
            time_in_phase = elapsed_time - self.phase_start_time
            signal = self.baseline + (self.association_rate * time_in_phase / 60)
        elif self.current_phase == "dissociation":
            # Start from end of association
            time_in_phase = elapsed_time - self.phase_start_time
            association_end = getattr(self, '_association_end', self.baseline)
            signal = association_end + (self.dissociation_rate * time_in_phase / 60)
        else:
            signal = self.baseline
            
        # Add noise to signal
        spr_value = signal + noise
        
        # Return data for all 4 channels (simulate slight differences)
        return {
            'a': spr_value,
            'b': spr_value + np.random.normal(0, 1),
            'c': spr_value + np.random.normal(0, 1.5),
            'd': spr_value + np.random.normal(0, 0.8)
        }
    
    def set_phase(self, phase, current_time):
        """Change the current phase (baseline, association, dissociation).
        
        Args:
            phase: Phase name
            current_time: Current time in seconds
        """
        if phase == "association" and self.current_phase != "association":
            self.phase_start_time = current_time
        elif phase == "dissociation" and self.current_phase != "dissociation":
            self.phase_start_time = current_time
            # Store the association end level
            self._association_end = self.baseline + (self.association_rate * 5)  # Assume 5 min association
        
        self.current_phase = phase
        logger.info(f"🎭 Simulation: Switched to {phase} phase at t={current_time:.1f}s")


def patch_application_for_simulation(app):
    """Patch the application to use simulated data.
    
    Args:
        app: Application instance to patch
    """
    logger.info("🎭 SIMULATION MODE ENABLED")
    logger.info("=" * 80)
    logger.info("Testing queue workflow with simulated SPR data")
    logger.info("No hardware required - all data is generated")
    logger.info("=" * 80)
    
    # Create data generator
    app._sim_generator = SimulatedDataGenerator()
    app._sim_start_time = time.time()
    app._sim_timer = QTimer()
    
    def simulate_data_acquisition():
        """Generate and inject simulated data."""
        if not hasattr(app.data_mgr, '_acquiring') or not app.data_mgr._acquiring:
            return
            
        elapsed = time.time() - app._sim_start_time
        
        # Generate data point
        data_point = app._sim_generator.get_data_point(elapsed)
        
        # Inject into data manager (simulate what detector would send)
        if hasattr(app.data_mgr, 'cycle_time'):
            app.data_mgr.cycle_time.append(elapsed)
            
            # Add data for each channel
            for ch in ['a', 'b', 'c', 'd']:
                channel_data = getattr(app.data_mgr, f'live_spr_{ch}', [])
                if isinstance(channel_data, list):
                    channel_data.append(data_point[ch])
                    setattr(app.data_mgr, f'live_spr_{ch}', channel_data)
            
            # Emit data signal if available
            if hasattr(app.data_mgr, 'data_ready'):
                app.data_mgr.data_ready.emit()
    
    # Start simulation timer (100 Hz = every 10ms)
    app._sim_timer.timeout.connect(simulate_data_acquisition)
    app._sim_timer.start(10)
    
    # Auto-detect simulated detector
    def auto_connect_simulation():
        """Auto-connect to simulated detector."""
        logger.info("🔌 Auto-connecting to simulated detector...")
        
        # Simulate detector connection
        if hasattr(app, 'detector_mgr'):
            app.detector_mgr._connected = True
            app.detector_mgr.device_serial = "SIM-DETECTOR-001"
            logger.info("✓ Simulated detector connected: SIM-DETECTOR-001")
        
        # Auto-start acquisition
        QTimer.singleShot(500, auto_start_acquisition)
    
    def auto_start_acquisition():
        """Auto-start data acquisition."""
        logger.info("📊 Auto-starting simulated data acquisition...")
        
        if hasattr(app, 'acquisition_events'):
            app.acquisition_events.on_start_button_clicked()
            logger.info("✓ Simulated acquisition started")
            logger.info("")
            logger.info("Ready to test! Try:")
            logger.info("  1. Click 'Build Method' to add cycles")
            logger.info("  2. Click 'Start Run' to execute queue")
            logger.info("  3. Watch intelligence bar for live countdown")
            logger.info("  4. See blue markers on Full Sensorgram")
            logger.info("  5. Check Cycle Data Table for completed cycles")
            logger.info("")
    
    # Trigger auto-connection after UI loads
    QTimer.singleShot(2000, auto_connect_simulation)
    
    # Override cycle phase detection
    original_on_start = app._on_start_button_clicked
    
    def simulated_on_start():
        """Start cycle with simulated phase detection."""
        # Call original
        result = original_on_start()
        
        # Update simulation phase based on cycle type
        if app._current_cycle:
            cycle_type = app._current_cycle.type.lower()
            if 'baseline' in cycle_type:
                app._sim_generator.set_phase("baseline", time.time() - app._sim_start_time)
            elif 'association' in cycle_type or 'concentration' in cycle_type:
                app._sim_generator.set_phase("association", time.time() - app._sim_start_time)
            elif 'dissociation' in cycle_type:
                app._sim_generator.set_phase("dissociation", time.time() - app._sim_start_time)
        
        return result
    
    app._on_start_button_clicked = simulated_on_start
    
    logger.info("✓ Simulation patches applied")


def main():
    """Run application in simulation mode."""
    # Create main application (Application inherits from QApplication)
    app = Application(sys.argv)
    
    # Apply simulation patches
    patch_application_for_simulation(app)
    
    # Show main window
    app.main_window.show()
    
    # Show info dialog
    QTimer.singleShot(3000, lambda: QMessageBox.information(
        app.main_window,
        "🎭 Simulation Mode Active",
        "<b>Simulation Mode Enabled</b><br><br>"
        "All SPR data is simulated - no hardware required!<br><br>"
        "<b>Test the workflow:</b><br>"
        "1. Click <b>'Build Method'</b> to add cycles<br>"
        "2. Add Baseline (3 min), Association (5 min), Dissociation (3 min)<br>"
        "3. Click <b>'Start Run'</b> to execute queue<br>"
        "4. Watch intelligence bar update with countdown<br>"
        "5. See blue cycle markers on Full Sensorgram<br>"
        "6. Check Cycle Data Table when complete<br><br>"
        "<i>Data acquisition is already running!</i>"
    ))
    
    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
