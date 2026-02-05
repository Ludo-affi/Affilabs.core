"""Example: Integrating Data Preprocessing into Affilabs.analyze UI

Shows how to add preprocessing controls to the Data tab before fitting.
"""

import sys
import numpy as np
import pandas as pd
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QPushButton, QLabel, QDoubleSpinBox, QCheckBox,
    QComboBox, QSpinBox
)
from spr_data_preprocessing import SPRPreprocessor


class DataPreprocessingPanel(QWidget):
    """Panel with preprocessing controls for SPR data."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.preprocessor = None
        self.original_data = None
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup preprocessing controls UI."""
        layout = QVBoxLayout(self)
        
        # === BASELINE CORRECTION ===
        baseline_group = QGroupBox("1. Baseline Correction")
        baseline_layout = QVBoxLayout(baseline_group)
        
        row1 = QHBoxLayout()
        self.baseline_enable = QCheckBox("Enable")
        self.baseline_enable.setChecked(True)
        row1.addWidget(self.baseline_enable)
        
        row1.addWidget(QLabel("Start:"))
        self.baseline_start = QDoubleSpinBox()
        self.baseline_start.setRange(0, 10000)
        self.baseline_start.setValue(0)
        self.baseline_start.setSuffix(" s")
        row1.addWidget(self.baseline_start)
        
        row1.addWidget(QLabel("End:"))
        self.baseline_end = QDoubleSpinBox()
        self.baseline_end.setRange(0, 10000)
        self.baseline_end.setValue(50)
        self.baseline_end.setSuffix(" s")
        row1.addWidget(self.baseline_end)
        
        baseline_layout.addLayout(row1)
        layout.addWidget(baseline_group)
        
        # === ZEROING ===
        zero_group = QGroupBox("2. Y-Axis Zeroing")
        zero_layout = QVBoxLayout(zero_group)
        
        row2 = QHBoxLayout()
        self.zero_enable = QCheckBox("Enable")
        self.zero_enable.setChecked(True)
        row2.addWidget(self.zero_enable)
        
        row2.addWidget(QLabel("Zero at:"))
        self.zero_time = QDoubleSpinBox()
        self.zero_time.setRange(0, 10000)
        self.zero_time.setValue(60)
        self.zero_time.setSuffix(" s")
        row2.addWidget(self.zero_time)
        
        row2.addWidget(QLabel("Window:"))
        self.zero_window = QDoubleSpinBox()
        self.zero_window.setRange(1, 100)
        self.zero_window.setValue(5)
        self.zero_window.setSuffix(" s")
        row2.addWidget(self.zero_window)
        
        zero_layout.addLayout(row2)
        layout.addWidget(zero_group)
        
        # === SMOOTHING ===
        smooth_group = QGroupBox("3. Smoothing")
        smooth_layout = QVBoxLayout(smooth_group)
        
        row3 = QHBoxLayout()
        self.smooth_enable = QCheckBox("Enable")
        row3.addWidget(self.smooth_enable)
        
        row3.addWidget(QLabel("Method:"))
        self.smooth_method = QComboBox()
        self.smooth_method.addItems(["Savitzky-Golay", "Moving Average", "None"])
        row3.addWidget(self.smooth_method)
        
        row3.addWidget(QLabel("Window:"))
        self.smooth_window = QSpinBox()
        self.smooth_window.setRange(3, 51)
        self.smooth_window.setValue(11)
        self.smooth_window.setSingleStep(2)  # Keep odd
        row3.addWidget(self.smooth_window)
        
        smooth_layout.addLayout(row3)
        layout.addWidget(smooth_group)
        
        # === OUTLIER REMOVAL ===
        outlier_group = QGroupBox("4. Outlier Removal")
        outlier_layout = QVBoxLayout(outlier_group)
        
        row4 = QHBoxLayout()
        self.outlier_enable = QCheckBox("Enable")
        row4.addWidget(self.outlier_enable)
        
        row4.addWidget(QLabel("Z-score threshold:"))
        self.outlier_threshold = QDoubleSpinBox()
        self.outlier_threshold.setRange(1.0, 5.0)
        self.outlier_threshold.setValue(3.0)
        self.outlier_threshold.setSingleStep(0.5)
        row4.addWidget(self.outlier_threshold)
        
        outlier_layout.addLayout(row4)
        layout.addWidget(outlier_group)
        
        # === REFERENCE SUBTRACTION ===
        ref_group = QGroupBox("5. Reference Subtraction")
        ref_layout = QVBoxLayout(ref_group)
        
        row5 = QHBoxLayout()
        self.ref_enable = QCheckBox("Enable")
        row5.addWidget(self.ref_enable)
        
        row5.addWidget(QLabel("Reference channel:"))
        self.ref_channel = QComboBox()
        self.ref_channel.addItems(["Channel A", "Channel B", "Channel C", "Channel D"])
        row5.addWidget(self.ref_channel)
        
        ref_layout.addLayout(row5)
        
        self.double_ref = QCheckBox("Double referencing (subtract blank injection too)")
        ref_layout.addWidget(self.double_ref)
        
        layout.addWidget(ref_group)
        
        # === TIME RANGE ===
        range_group = QGroupBox("6. Time Range Selection")
        range_layout = QVBoxLayout(range_group)
        
        row6 = QHBoxLayout()
        self.range_enable = QCheckBox("Enable")
        row6.addWidget(self.range_enable)
        
        row6.addWidget(QLabel("From:"))
        self.range_start = QDoubleSpinBox()
        self.range_start.setRange(0, 10000)
        self.range_start.setValue(60)
        self.range_start.setSuffix(" s")
        row6.addWidget(self.range_start)
        
        row6.addWidget(QLabel("To:"))
        self.range_end = QDoubleSpinBox()
        self.range_end.setRange(0, 10000)
        self.range_end.setValue(360)
        self.range_end.setSuffix(" s")
        row6.addWidget(self.range_end)
        
        range_layout.addLayout(row6)
        layout.addWidget(range_group)
        
        # === ACTION BUTTONS ===
        button_layout = QHBoxLayout()
        
        self.apply_btn = QPushButton("✓ Apply Preprocessing")
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #34C759;
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #30B350;
            }
        """)
        self.apply_btn.clicked.connect(self.apply_preprocessing)
        button_layout.addWidget(self.apply_btn)
        
        self.reset_btn = QPushButton("↺ Reset")
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9500;
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #E68600;
            }
        """)
        self.reset_btn.clicked.connect(self.reset_preprocessing)
        button_layout.addWidget(self.reset_btn)
        
        layout.addLayout(button_layout)
        
        # === SUMMARY ===
        self.summary_label = QLabel("No preprocessing applied")
        self.summary_label.setStyleSheet("""
            background: #F5F5F7;
            padding: 12px;
            border-radius: 6px;
            color: #1D1D1F;
            font-family: monospace;
            font-size: 11px;
        """)
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        
        layout.addStretch()
    
    def load_data(self, time: np.ndarray, response: np.ndarray):
        """Load raw data for preprocessing.
        
        Args:
            time: Time array (seconds)
            response: Response array (RU or nm)
        """
        self.original_data = (time.copy(), response.copy())
        self.preprocessor = SPRPreprocessor(time, response)
        self.summary_label.setText("Data loaded - ready for preprocessing")
    
    def apply_preprocessing(self):
        """Apply selected preprocessing steps."""
        if self.preprocessor is None:
            self.summary_label.setText("⚠️ No data loaded")
            return
        
        # Reset to original data
        self.preprocessor.reset()
        
        try:
            # Apply each enabled step
            if self.baseline_enable.isChecked():
                self.preprocessor.baseline_correction(
                    self.baseline_start.value(),
                    self.baseline_end.value()
                )
            
            if self.zero_enable.isChecked():
                self.preprocessor.zero_at_time(
                    self.zero_time.value(),
                    self.zero_window.value()
                )
            
            if self.smooth_enable.isChecked():
                method = self.smooth_method.currentText()
                if method == "Savitzky-Golay":
                    self.preprocessor.smooth(window_length=self.smooth_window.value())
                elif method == "Moving Average":
                    self.preprocessor.moving_average(window_size=self.smooth_window.value())
            
            if self.outlier_enable.isChecked():
                self.preprocessor.remove_outliers(
                    threshold=self.outlier_threshold.value()
                )
            
            if self.range_enable.isChecked():
                self.preprocessor.trim_time_range(
                    self.range_start.value(),
                    self.range_end.value()
                )
            
            # Update summary
            self.summary_label.setText(self.preprocessor.get_processing_summary())
            
            # Emit signal or call callback to update plots
            self.update_plots()
            
        except Exception as e:
            self.summary_label.setText(f"❌ Error: {str(e)}")
    
    def reset_preprocessing(self):
        """Reset to original data."""
        if self.preprocessor:
            self.preprocessor.reset()
            self.summary_label.setText("Reset to original data")
            self.update_plots()
    
    def get_processed_data(self):
        """Get current processed data.
        
        Returns:
            (time_array, response_array) or None if no data
        """
        if self.preprocessor:
            return self.preprocessor.get_processed_data()
        return None
    
    def update_plots(self):
        """Update plots with processed data (override in subclass)."""
        # This would be connected to the plot widget
        print("Plot updated with processed data")


# ============================================================================
# EXAMPLE: Integration with Analyze UI
# ============================================================================

def integrate_preprocessing_into_analyze_ui():
    """
    Example of how to add preprocessing panel to Affilabs.analyze Data tab.
    
    In affilabs_analyze_prototype.py, modify the DataTab class:
    """
    
    code_example = '''
class DataTab(QWidget):
    """Tab 1: Data import and visualization."""
    
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)  # Changed to horizontal
        
        # Left side: Preprocessing panel
        self.preprocess_panel = DataPreprocessingPanel()
        self.preprocess_panel.setMaximumWidth(400)
        layout.addWidget(self.preprocess_panel)
        
        # Right side: Plots and table (existing code)
        right_layout = QVBoxLayout()
        
        # Main sensorgram plot
        self.plot = SensogramPlot()
        right_layout.addWidget(self.plot, stretch=2)
        
        # Data table (existing code)
        # ...
        
        layout.addLayout(right_layout)
        
        # Connect preprocessing to plot updates
        self.preprocess_panel.update_plots = self._refresh_plot
    
    def _refresh_plot(self):
        """Refresh plot with processed data."""
        processed = self.preprocess_panel.get_processed_data()
        if processed:
            t, R = processed
            self.plot.clear_curves()
            self.plot.add_curve(t, R, "Processed", "#0066CC")
    
    def _on_data_imported(self, time, response):
        """Called when new data is imported."""
        # Load into preprocessing panel
        self.preprocess_panel.load_data(time, response)
        
        # Show original data
        self.plot.add_curve(time, response, "Original", "#CCCCCC")
    '''
    
    print("=" * 80)
    print("INTEGRATION EXAMPLE")
    print("=" * 80)
    print(code_example)
    print("\nThis adds a preprocessing panel to the Data tab that allows users to:")
    print("  1. Correct baseline before analysis")
    print("  2. Zero Y-axis at injection start")
    print("  3. Smooth noisy data")
    print("  4. Remove outliers/spikes")
    print("  5. Subtract reference channels")
    print("  6. Select time ranges for fitting")


if __name__ == "__main__":
    # Demo the preprocessing panel
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("SPR Data Preprocessing Demo")
    window.resize(450, 900)
    
    panel = DataPreprocessingPanel()
    window.setCentralWidget(panel)
    
    # Load demo data
    t = np.linspace(0, 600, 600)
    R = 5 + 0.01*t + 50*(1 - np.exp(-0.01*(t-100))) * (t > 100)
    R += np.random.normal(0, 2, len(t))
    
    panel.load_data(t, R)
    
    window.show()
    
    print("\n" + "="*80)
    print("SPR DATA PREPROCESSING PANEL")
    print("="*80)
    print("\nControls available:")
    print("  • Baseline correction (subtract pre-injection baseline)")
    print("  • Y-axis zeroing (set injection start to zero)")
    print("  • Smoothing (Savitzky-Golay or moving average)")
    print("  • Outlier removal (z-score based)")
    print("  • Reference subtraction (single or double)")
    print("  • Time range selection (trim to analysis region)")
    print("\nClick 'Apply Preprocessing' to process data")
    print("Click 'Reset' to restore original data")
    print("="*80)
    
    sys.exit(app.exec())
