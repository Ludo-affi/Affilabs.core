"""Affilabs.analyze UI Prototype

A working prototype to visualize the Affilabs.analyze interface.
Run this file to see the UI in action.

Usage:
    python affilabs_analyze_prototype.py
"""

import sys
import numpy as np
import pandas as pd
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QLabel,
    QFrame,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QRadioButton,
    QButtonGroup,
    QGroupBox,
    QLineEdit,
    QTextEdit,
    QScrollArea,
    QToolBar,
    QStatusBar,
    QHeaderView,
    QSizePolicy,
    QFileDialog,
    QMessageBox,
)

# Try to import pyqtgraph for plotting
try:
    import pyqtgraph as pg
    HAS_PYQTGRAPH = True
    pg.setConfigOptions(antialias=True, background='w', foreground='k')
except ImportError:
    HAS_PYQTGRAPH = False
    print("Note: pyqtgraph not installed. Using placeholder plots.")


# ============================================================================
# STYLE CONSTANTS (matching Affilabs.core exactly)
# ============================================================================

class Colors:
    """Color constants following Apple's design system - matches affilabs/ui_styles.py"""
    
    # Neutral colors (from Affilabs.core)
    PRIMARY_TEXT = "#1D1D1F"
    SECONDARY_TEXT = "#86868B"
    BACKGROUND_WHITE = "#FFFFFF"
    BACKGROUND_LIGHT = "#F5F5F7"
    TRANSPARENT = "transparent"
    
    # Semantic colors
    SUCCESS = "#34C759"
    WARNING = "#FF9500"
    ERROR = "#FF3B30"
    INFO = "#007AFF"
    
    # Alpha overlays (for backgrounds)
    OVERLAY_LIGHT_3 = "rgba(0, 0, 0, 0.03)"
    OVERLAY_LIGHT_4 = "rgba(0, 0, 0, 0.04)"
    OVERLAY_LIGHT_6 = "rgba(0, 0, 0, 0.06)"
    OVERLAY_LIGHT_8 = "rgba(0, 0, 0, 0.08)"
    OVERLAY_LIGHT_10 = "rgba(0, 0, 0, 0.1)"
    OVERLAY_LIGHT_20 = "rgba(0, 0, 0, 0.2)"
    OVERLAY_LIGHT_30 = "rgba(0, 0, 0, 0.3)"
    
    # Button colors (dark buttons like Affilabs.core)
    BUTTON_PRIMARY = "#1D1D1F"
    BUTTON_PRIMARY_HOVER = "#3A3A3C"
    BUTTON_PRIMARY_PRESSED = "#48484A"
    BUTTON_DISABLED = "#86868B"
    
    # Border
    BORDER = "rgba(0, 0, 0, 0.1)"


class Fonts:
    """Font family constants - matches affilabs/ui_styles.py"""
    SYSTEM = "-apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif"
    DISPLAY = "-apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif"
    MONOSPACE = "-apple-system, 'SF Mono', 'Menlo', monospace"


# Concentration color palette (colorblind-safe - Tol bright scheme)
CONC_COLORS = [
    "#4477AA",  # Blue (highest conc)
    "#EE6677",  # Red
    "#228833",  # Green
    "#CCBB44",  # Yellow
    "#66CCEE",  # Cyan
    "#AA3377",  # Purple
]


STYLESHEET = f"""
    QMainWindow {{
        background: {Colors.BACKGROUND_LIGHT};
    }}
    QWidget {{
        font-family: {Fonts.SYSTEM};
        font-size: 13px;
        color: {Colors.PRIMARY_TEXT};
    }}
    
    /* Tab Widget - matching Affilabs.core horizontal tabs */
    QTabWidget::pane {{
        border: none;
        background: {Colors.BACKGROUND_WHITE};
        border-top: 1px solid {Colors.OVERLAY_LIGHT_10};
    }}
    QTabBar::tab {{
        background: transparent;
        color: {Colors.SECONDARY_TEXT};
        padding: 10px 24px;
        margin-right: 4px;
        border: none;
        font-size: 13px;
        font-weight: 500;
        border-bottom: 2px solid transparent;
    }}
    QTabBar::tab:selected {{
        background: transparent;
        color: {Colors.PRIMARY_TEXT};
        font-weight: 600;
        border-bottom: 2px solid {Colors.PRIMARY_TEXT};
    }}
    QTabBar::tab:hover:!selected {{
        color: {Colors.PRIMARY_TEXT};
        background: {Colors.OVERLAY_LIGHT_4};
    }}
    
    /* Primary Buttons - dark style like Affilabs.core */
    QPushButton {{
        background: {Colors.BUTTON_PRIMARY};
        color: white;
        border: none;
        border-radius: 8px;
        padding: 8px 16px;
        font-size: 13px;
        font-weight: 600;
        font-family: {Fonts.SYSTEM};
    }}
    QPushButton:hover {{
        background: {Colors.BUTTON_PRIMARY_HOVER};
    }}
    QPushButton:pressed {{
        background: {Colors.BUTTON_PRIMARY_PRESSED};
    }}
    QPushButton:disabled {{
        background: {Colors.BUTTON_DISABLED};
        color: white;
    }}
    
    /* Secondary Buttons - light style */
    QPushButton[secondary="true"] {{
        background: {Colors.OVERLAY_LIGHT_4};
        color: {Colors.PRIMARY_TEXT};
        border: none;
    }}
    QPushButton[secondary="true"]:hover {{
        background: {Colors.OVERLAY_LIGHT_8};
    }}
    QPushButton[secondary="true"]:pressed {{
        background: {Colors.OVERLAY_LIGHT_10};
    }}
    
    /* Group Box - matching Affilabs.core collapsible sections */
    QGroupBox {{
        font-weight: 600;
        font-size: 14px;
        border: none;
        border-radius: 8px;
        margin-top: 16px;
        padding: 16px 12px 12px 12px;
        background: {Colors.OVERLAY_LIGHT_3};
        color: {Colors.PRIMARY_TEXT};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 12px;
        top: 4px;
        padding: 0 6px;
        color: {Colors.PRIMARY_TEXT};
        font-family: {Fonts.SYSTEM};
    }}
    
    /* Tree Widget - Project Explorer */
    QTreeWidget {{
        border: 1px solid {Colors.OVERLAY_LIGHT_10};
        border-radius: 8px;
        background: {Colors.BACKGROUND_WHITE};
        outline: none;
    }}
    QTreeWidget::item {{
        padding: 6px 4px;
        border-radius: 4px;
    }}
    QTreeWidget::item:selected {{
        background: {Colors.OVERLAY_LIGHT_8};
        color: {Colors.PRIMARY_TEXT};
    }}
    QTreeWidget::item:hover:!selected {{
        background: {Colors.OVERLAY_LIGHT_4};
    }}
    
    /* Table Widget */
    QTableWidget {{
        border: 1px solid {Colors.OVERLAY_LIGHT_10};
        border-radius: 8px;
        background: {Colors.BACKGROUND_WHITE};
        gridline-color: {Colors.OVERLAY_LIGHT_6};
        outline: none;
    }}
    QTableWidget::item {{
        padding: 4px 8px;
    }}
    QTableWidget::item:selected {{
        background: {Colors.OVERLAY_LIGHT_8};
        color: {Colors.PRIMARY_TEXT};
    }}
    QHeaderView::section {{
        background: {Colors.BACKGROUND_LIGHT};
        border: none;
        border-bottom: 1px solid {Colors.OVERLAY_LIGHT_10};
        padding: 8px 12px;
        font-weight: 600;
        font-size: 12px;
        color: {Colors.SECONDARY_TEXT};
    }}
    
    /* ComboBox */
    QComboBox {{
        border: 1px solid {Colors.OVERLAY_LIGHT_20};
        border-radius: 6px;
        padding: 6px 12px;
        background: {Colors.BACKGROUND_WHITE};
        font-family: {Fonts.SYSTEM};
    }}
    QComboBox:hover {{
        border-color: {Colors.OVERLAY_LIGHT_30};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background: {Colors.BACKGROUND_WHITE};
        border: 1px solid {Colors.OVERLAY_LIGHT_20};
        border-radius: 6px;
        selection-background-color: {Colors.OVERLAY_LIGHT_8};
    }}
    
    /* Input Fields */
    QLineEdit, QSpinBox, QDoubleSpinBox {{
        border: 1px solid {Colors.OVERLAY_LIGHT_20};
        border-radius: 6px;
        padding: 6px 12px;
        background: {Colors.BACKGROUND_WHITE};
        font-family: {Fonts.SYSTEM};
    }}
    QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
        border-color: {Colors.OVERLAY_LIGHT_30};
    }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
        border-color: {Colors.PRIMARY_TEXT};
    }}
    
    /* Checkbox - matching Affilabs.core */
    QCheckBox {{
        font-size: 13px;
        color: {Colors.PRIMARY_TEXT};
        background: transparent;
        spacing: 6px;
        font-weight: 500;
        font-family: {Fonts.SYSTEM};
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border: 1.5px solid {Colors.OVERLAY_LIGHT_20};
        border-radius: 4px;
        background: white;
    }}
    QCheckBox::indicator:hover {{
        border-color: {Colors.OVERLAY_LIGHT_30};
    }}
    QCheckBox::indicator:checked {{
        background: {Colors.BUTTON_PRIMARY};
        border-color: {Colors.BUTTON_PRIMARY};
    }}
    
    /* Radio Button - matching Affilabs.core */
    QRadioButton {{
        font-size: 13px;
        color: {Colors.PRIMARY_TEXT};
        background: transparent;
        spacing: 6px;
        font-family: {Fonts.SYSTEM};
    }}
    QRadioButton::indicator {{
        width: 16px;
        height: 16px;
        border: 1.5px solid {Colors.OVERLAY_LIGHT_20};
        border-radius: 9px;
        background: white;
    }}
    QRadioButton::indicator:checked {{
        background: {Colors.BUTTON_PRIMARY};
        border: 4px solid white;
        outline: 1.5px solid {Colors.BUTTON_PRIMARY};
    }}
    
    /* Scrollbar - matching Affilabs.core */
    QScrollBar:vertical {{
        background: {Colors.BACKGROUND_LIGHT};
        width: 10px;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical {{
        background: {Colors.OVERLAY_LIGHT_20};
        border-radius: 5px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {Colors.OVERLAY_LIGHT_30};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    
    /* Status Bar */
    QStatusBar {{
        background: {Colors.BACKGROUND_WHITE};
        border-top: 1px solid {Colors.OVERLAY_LIGHT_10};
        color: {Colors.SECONDARY_TEXT};
        font-size: 12px;
    }}
    
    /* Splitter Handle */
    QSplitter::handle {{
        background: {Colors.OVERLAY_LIGHT_6};
    }}
    QSplitter::handle:hover {{
        background: {Colors.OVERLAY_LIGHT_10};
    }}
"""


# ============================================================================
# SIMULATED DATA
# ============================================================================

def generate_sensorgram(conc_nM, ka=1.2e5, kd=2.3e-4, Rmax=850, noise=5):
    """Generate simulated SPR sensorgram data."""
    # Time points
    t_baseline = np.linspace(0, 60, 600)
    t_assoc = np.linspace(60, 180, 1200)
    t_dissoc = np.linspace(180, 400, 2200)
    
    # Baseline
    baseline = np.zeros_like(t_baseline) + np.random.normal(0, noise, len(t_baseline))
    
    # Association phase (1:1 Langmuir)
    C = conc_nM * 1e-9  # Convert to M
    kobs = ka * C + kd
    Req = (ka * C * Rmax) / kobs
    assoc = Req * (1 - np.exp(-kobs * (t_assoc - 60)))
    assoc += np.random.normal(0, noise, len(assoc))
    
    # Dissociation phase
    R0 = assoc[-1]
    dissoc = R0 * np.exp(-kd * (t_dissoc - 180))
    dissoc += np.random.normal(0, noise, len(dissoc))
    
    t = np.concatenate([t_baseline, t_assoc, t_dissoc])
    R = np.concatenate([baseline, assoc, dissoc])
    
    return t, R


# ============================================================================
# PLOT WIDGETS
# ============================================================================

class PlaceholderPlot(QFrame):
    """Placeholder when pyqtgraph is not available."""
    
    def __init__(self, title="Plot"):
        super().__init__()
        self.title = title
        self.setMinimumHeight(200)
        self.setStyleSheet(f"background: white; border: 1px solid {Colors.OVERLAY_LIGHT_10}; border-radius: 8px;")
    
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw border
        painter.setPen(QPen(QColor(Colors.OVERLAY_LIGHT_20), 1))
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 8, 8)
        
        # Draw title
        painter.setPen(QColor(Colors.PRIMARY_TEXT))
        painter.setFont(QFont(Fonts.SYSTEM.split(",")[0].strip("'"), 12, QFont.Bold))
        painter.drawText(self.rect(), Qt.AlignCenter, f"📊 {self.title}\n\n(Install pyqtgraph for live plots)")


class SensogramPlot(QWidget):
    """Sensorgram overlay plot widget."""
    
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        if HAS_PYQTGRAPH:
            self.plot_widget = pg.PlotWidget()
            self.plot_widget.setLabel('left', 'Response', units='RU')
            self.plot_widget.setLabel('bottom', 'Time', units='s')
            self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
            self.plot_widget.setBackground('w')
            self.plot_widget.addLegend()
            layout.addWidget(self.plot_widget)
            self.curves = []
        else:
            self.plot_widget = PlaceholderPlot("Sensorgram Overlay")
            layout.addWidget(self.plot_widget)
    
    def add_curve(self, t, R, name, color):
        """Add a sensorgram curve."""
        if HAS_PYQTGRAPH:
            pen = pg.mkPen(color=color, width=2)
            curve = self.plot_widget.plot(t, R, pen=pen, name=name)
            self.curves.append(curve)
    
    def clear_curves(self):
        """Clear all curves."""
        if HAS_PYQTGRAPH:
            self.plot_widget.clear()
            self.curves = []


class FittingPlot(QWidget):
    """Fitting plot with residuals."""
    
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        if HAS_PYQTGRAPH:
            # Main plot
            self.main_plot = pg.PlotWidget()
            self.main_plot.setLabel('left', 'Response', units='RU')
            self.main_plot.showGrid(x=True, y=True, alpha=0.3)
            self.main_plot.setBackground('w')
            layout.addWidget(self.main_plot, stretch=3)
            
            # Residuals plot
            self.residual_plot = pg.PlotWidget()
            self.residual_plot.setLabel('left', 'Residual')
            self.residual_plot.setLabel('bottom', 'Time', units='s')
            self.residual_plot.showGrid(x=True, y=True, alpha=0.3)
            self.residual_plot.setBackground('w')
            self.residual_plot.setMaximumHeight(100)
            layout.addWidget(self.residual_plot, stretch=1)
            
            # Link x-axes
            self.residual_plot.setXLink(self.main_plot)
        else:
            layout.addWidget(PlaceholderPlot("Fitting Plot + Residuals"))
    
    def plot_fit(self, t, R_exp, R_fit, color):
        """Plot experimental data and fit."""
        if HAS_PYQTGRAPH:
            self.main_plot.clear()
            self.residual_plot.clear()
            
            # Experimental
            self.main_plot.plot(t, R_exp, pen=None, symbol='o', symbolSize=3, 
                              symbolBrush=color, name='Experimental')
            # Fitted
            self.main_plot.plot(t, R_fit, pen=pg.mkPen(color='k', width=2), name='Fitted')
            
            # Residuals
            residuals = R_exp - R_fit
            self.residual_plot.plot(t, residuals, pen=pg.mkPen(color=color, width=1))
            self.residual_plot.addLine(y=0, pen=pg.mkPen(color='k', width=1, style=Qt.DashLine))


# ============================================================================
# MAIN WINDOW PANELS
# ============================================================================

class ProjectExplorer(QWidget):
    """Left panel - Project tree and quick stats."""
    
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background: {Colors.BACKGROUND_WHITE};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(12)
        
        # Title - matching Affilabs.core section headers
        title = QLabel("PROJECT EXPLORER")
        title.setStyleSheet(f"""
            font-weight: 700;
            color: {Colors.SECONDARY_TEXT};
            font-size: 11px;
            letter-spacing: 0.5px;
            background: transparent;
            font-family: {Fonts.SYSTEM};
        """)
        layout.addWidget(title)
        
        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(16)
        layout.addWidget(self.tree)
        
        # Populate with demo data
        self._populate_demo_data()
        
        # Quick stats section - styled like Affilabs.core collapsible sections
        stats_group = QGroupBox("QUICK STATS")
        stats_layout = QVBoxLayout(stats_group)
        stats_layout.setSpacing(8)
        
        self.stats_labels = {}
        for label, value in [("Runs:", "5"), ("Fitted:", "0/5"), ("KD range:", "—")]:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {Colors.SECONDARY_TEXT}; background: transparent; font-size: 13px;")
            val = QLabel(value)
            val.setStyleSheet(f"font-weight: 600; background: transparent; font-size: 13px;")
            self.stats_labels[label] = val
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(val)
            stats_layout.addLayout(row)
        
        layout.addWidget(stats_group)
    
    def _populate_demo_data(self):
        """Add demo project structure."""
        project = QTreeWidgetItem(self.tree, ["📁 Demo Project"])
        project.setExpanded(True)
        
        study1 = QTreeWidgetItem(project, ["📁 Anti-HER2 Study"])
        study1.setExpanded(True)
        
        concentrations = ["100 nM", "50 nM", "25 nM", "12.5 nM", "6.25 nM"]
        for conc in concentrations:
            QTreeWidgetItem(study1, [f"📄 {conc}"])
    
    def update_stats(self, runs, fitted, kd_range):
        """Update quick stats display."""
        self.stats_labels["Runs:"].setText(str(runs))
        self.stats_labels["Fitted:"].setText(f"{fitted}/{runs}")
        self.stats_labels["KD range:"].setText(kd_range)


class PropertiesPanel(QWidget):
    """Right panel - Selected item properties."""
    
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background: {Colors.BACKGROUND_WHITE};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(12)
        
        # Title - matching Affilabs.core section headers
        title = QLabel("PROPERTIES")
        title.setStyleSheet(f"""
            font-weight: 700;
            color: {Colors.SECONDARY_TEXT};
            font-size: 11px;
            letter-spacing: 0.5px;
            background: transparent;
            font-family: {Fonts.SYSTEM};
        """)
        layout.addWidget(title)
        
        # Selected item
        self.selected_label = QLabel("Selected: None")
        self.selected_label.setStyleSheet(f"font-weight: 600; font-size: 14px; background: transparent;")
        layout.addWidget(self.selected_label)
        
        layout.addSpacing(8)
        
        # Properties list - styled like Affilabs.core
        props_group = QGroupBox("Details")
        props_layout = QVBoxLayout(props_group)
        props_layout.setSpacing(8)
        
        self.prop_labels = {}
        properties = [
            ("Channels:", "4"),
            ("Duration:", "—"),
            ("Points:", "—"),
            ("Concentration:", "—"),
            ("Analyte:", "—"),
            ("Fit Status:", "⏳ Pending"),
        ]
        
        for label, value in properties:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {Colors.SECONDARY_TEXT}; background: transparent; font-size: 13px;")
            val = QLabel(value)
            val.setStyleSheet(f"background: transparent; font-size: 13px;")
            self.prop_labels[label] = val
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(val)
            props_layout.addLayout(row)
        
        layout.addWidget(props_group)
        layout.addStretch()
    
    def set_selected(self, name, properties=None):
        """Update selected item display."""
        self.selected_label.setText(f"Selected: {name}")
        if properties:
            for key, value in properties.items():
                if key in self.prop_labels:
                    self.prop_labels[key].setText(str(value))


# ============================================================================
# TAB CONTENT WIDGETS
# ============================================================================

class DataTab(QWidget):
    """Tab 1: Data import and visualization."""
    
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Main sensorgram plot
        self.plot = SensogramPlot()
        layout.addWidget(self.plot, stretch=2)
        
        # Bottom controls
        bottom = QHBoxLayout()
        
        # Alignment controls
        align_group = QGroupBox("Alignment Controls")
        align_layout = QVBoxLayout(align_group)
        
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Align to:"))
        self.align_combo = QComboBox()
        self.align_combo.addItems(["Injection Start", "Association Start", "Manual"])
        row1.addWidget(self.align_combo)
        align_layout.addLayout(row1)
        
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Y-Axis:"))
        y_group = QButtonGroup(self)
        for i, text in enumerate(["Absolute (RU)", "Normalized (%)", "Baseline-sub"]):
            rb = QRadioButton(text)
            if i == 0:
                rb.setChecked(True)
            y_group.addButton(rb)
            row2.addWidget(rb)
        align_layout.addLayout(row2)
        
        apply_btn = QPushButton("Apply Baseline Correction")
        apply_btn.setProperty("secondary", True)
        align_layout.addWidget(apply_btn)
        
        bottom.addWidget(align_group)
        
        # Data table
        table_group = QGroupBox("Data Table")
        table_layout = QVBoxLayout(table_group)
        
        self.data_table = QTableWidget(5, 5)
        self.data_table.setHorizontalHeaderLabels(["Run", "Conc", "Ch", "Rmax", "Status"])
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.data_table.setMaximumHeight(180)
        
        # Populate demo data
        demo_data = [
            ("☑ Run1", "100 nM", "A", "823", "✓ OK"),
            ("☑ Run2", "50 nM", "A", "612", "✓ OK"),
            ("☑ Run3", "25 nM", "A", "445", "✓ OK"),
            ("☑ Run4", "12.5 nM", "A", "298", "✓ OK"),
            ("☐ Run5", "6.25 nM", "A", "52", "⚠ Low"),
        ]
        for row, data in enumerate(demo_data):
            for col, value in enumerate(data):
                item = QTableWidgetItem(value)
                if col == 4 and "⚠" in value:
                    item.setForeground(QColor(Colors.WARNING))
                self.data_table.setItem(row, col, item)
        
        table_layout.addWidget(self.data_table)
        
        btn_row = QHBoxLayout()
        for text in ["Select All", "Invert", "Remove"]:
            btn = QPushButton(text)
            btn.setProperty("secondary", True)
            btn.setFixedWidth(80)
            btn_row.addWidget(btn)
        btn_row.addStretch()
        table_layout.addLayout(btn_row)
        
        bottom.addWidget(table_group)
        
        layout.addLayout(bottom)
        
        # Load demo data
        self._load_demo_data()
    
    def _load_demo_data(self):
        """Load demo sensorgram data."""
        concentrations = [100, 50, 25, 12.5, 6.25]
        for i, conc in enumerate(concentrations):
            t, R = generate_sensorgram(conc)
            self.plot.add_curve(t, R, f"{conc} nM", CONC_COLORS[i % len(CONC_COLORS)])


class FittingTab(QWidget):
    """Tab 2: Kinetic fitting."""
    
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Fitting plot with residuals
        self.plot = FittingPlot()
        layout.addWidget(self.plot, stretch=2)
        
        # Bottom section
        bottom = QHBoxLayout()
        
        # Fitting parameters
        params_group = QGroupBox("Fitting Parameters")
        params_layout = QVBoxLayout(params_group)
        
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "1:1 Langmuir",
            "1:1 + Mass Transport",
            "Heterogeneous (1:2)",
            "Bivalent Analyte",
        ])
        row1.addWidget(self.model_combo)
        params_layout.addLayout(row1)
        
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Mode:"))
        mode_group = QButtonGroup(self)
        global_rb = QRadioButton("Global")
        global_rb.setChecked(True)
        local_rb = QRadioButton("Local")
        mode_group.addButton(global_rb)
        mode_group.addButton(local_rb)
        row2.addWidget(global_rb)
        row2.addWidget(local_rb)
        row2.addStretch()
        params_layout.addLayout(row2)
        
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Association:"))
        self.assoc_start = QSpinBox()
        self.assoc_start.setRange(0, 1000)
        self.assoc_start.setValue(60)
        row3.addWidget(self.assoc_start)
        row3.addWidget(QLabel("-"))
        self.assoc_end = QSpinBox()
        self.assoc_end.setRange(0, 1000)
        self.assoc_end.setValue(180)
        row3.addWidget(self.assoc_end)
        row3.addWidget(QLabel("s"))
        params_layout.addLayout(row3)
        
        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Dissociation:"))
        self.dissoc_start = QSpinBox()
        self.dissoc_start.setRange(0, 1000)
        self.dissoc_start.setValue(180)
        row4.addWidget(self.dissoc_start)
        row4.addWidget(QLabel("-"))
        self.dissoc_end = QSpinBox()
        self.dissoc_end.setRange(0, 1000)
        self.dissoc_end.setValue(400)
        row4.addWidget(self.dissoc_end)
        row4.addWidget(QLabel("s"))
        params_layout.addLayout(row4)
        
        self.mass_transport_cb = QCheckBox("Mass transport (km)")
        params_layout.addWidget(self.mass_transport_cb)
        
        btn_row = QHBoxLayout()
        fit_btn = QPushButton("▶ Fit Selected")
        fit_btn.clicked.connect(self._run_fit)
        btn_row.addWidget(fit_btn)
        
        fit_all_btn = QPushButton("▶▶ Fit All")
        fit_all_btn.clicked.connect(self._run_fit)
        btn_row.addWidget(fit_all_btn)
        
        reset_btn = QPushButton("↺ Reset")
        reset_btn.setProperty("secondary", True)
        btn_row.addWidget(reset_btn)
        params_layout.addLayout(btn_row)
        
        bottom.addWidget(params_group)
        
        # Results panel
        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout(results_group)
        
        self.results_table = QTableWidget(6, 3)
        self.results_table.setHorizontalHeaderLabels(["Parameter", "Value", "Error"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.results_table.setMaximumHeight(200)
        
        # Pre-fill with placeholders
        params = [
            ("ka (1/Ms)", "—", "—"),
            ("kd (1/s)", "—", "—"),
            ("KD (nM)", "—", "—"),
            ("Rmax (RU)", "—", "—"),
            ("Chi² (χ²)", "—", ""),
            ("R²", "—", ""),
        ]
        for row, (p, v, e) in enumerate(params):
            self.results_table.setItem(row, 0, QTableWidgetItem(p))
            self.results_table.setItem(row, 1, QTableWidgetItem(v))
            self.results_table.setItem(row, 2, QTableWidgetItem(e))
        
        results_layout.addWidget(self.results_table)
        
        export_row = QHBoxLayout()
        for text in ["Export CSV", "Copy", "Add to Report"]:
            btn = QPushButton(text)
            btn.setProperty("secondary", True)
            export_row.addWidget(btn)
        results_layout.addLayout(export_row)
        
        bottom.addWidget(results_group)
        
        layout.addLayout(bottom)
        
        # Concentration summary table
        summary_group = QGroupBox("Concentration Series Summary")
        summary_layout = QVBoxLayout(summary_group)
        
        self.summary_table = QTableWidget(5, 7)
        self.summary_table.setHorizontalHeaderLabels(
            ["Conc (nM)", "ka (1/Ms)", "kd (1/s)", "KD (nM)", "Rmax", "χ²", "Incl"]
        )
        self.summary_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.summary_table.setMaximumHeight(160)
        
        # Populate with placeholders
        concs = ["100", "50", "25", "12.5", "6.25"]
        for row, conc in enumerate(concs):
            self.summary_table.setItem(row, 0, QTableWidgetItem(conc))
            for col in range(1, 6):
                self.summary_table.setItem(row, col, QTableWidgetItem("—"))
            cb_item = QTableWidgetItem("☑" if row < 4 else "☐")
            self.summary_table.setItem(row, 6, cb_item)
        
        summary_layout.addWidget(self.summary_table)
        layout.addWidget(summary_group)
    
    def _run_fit(self):
        """Run fitting (demo with simulated results)."""
        # Simulate fit results
        ka = 1.23e5 + np.random.normal(0, 0.05e5)
        kd = 2.34e-4 + np.random.normal(0, 0.1e-4)
        KD = kd / ka * 1e9  # Convert to nM
        Rmax = 856 + np.random.normal(0, 20)
        chi2 = 0.42 + np.random.normal(0, 0.1)
        r2 = 0.9987 + np.random.normal(0, 0.001)
        
        results = [
            (f"{ka:.2e}", f"± {ka*0.02:.1e}"),
            (f"{kd:.2e}", f"± {kd*0.05:.1e}"),
            (f"{KD:.2f}", f"± {KD*0.08:.2f}"),
            (f"{Rmax:.0f}", f"± {Rmax*0.015:.0f}"),
            (f"{chi2:.2f}", ""),
            (f"{r2:.4f}", ""),
        ]
        
        for row, (val, err) in enumerate(results):
            self.results_table.item(row, 1).setText(val)
            self.results_table.item(row, 2).setText(err)
        
        # Update summary table
        for row in range(4):
            self.summary_table.item(row, 1).setText(f"{ka + np.random.normal(0, 0.02e5):.2e}")
            self.summary_table.item(row, 2).setText(f"{kd + np.random.normal(0, 0.05e-4):.2e}")
            self.summary_table.item(row, 3).setText(f"{KD + np.random.normal(0, 0.1):.2f}")
            self.summary_table.item(row, 4).setText(f"{int(Rmax * (1 - row*0.2))}")
            self.summary_table.item(row, 5).setText(f"{chi2 + np.random.normal(0, 0.05):.2f}")
        
        # Plot fitted data
        if HAS_PYQTGRAPH:
            t, R_exp = generate_sensorgram(50)
            # Simulated fit (just smooth the data)
            from scipy.ndimage import uniform_filter1d
            R_fit = uniform_filter1d(R_exp, size=20)
            self.plot.plot_fit(t, R_exp, R_fit, CONC_COLORS[1])


class ReportTab(QWidget):
    """Tab 3: Report builder."""
    
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setSpacing(12)
        
        # Left: Components palette
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(180)
        
        title = QLabel("COMPONENTS")
        title.setStyleSheet(f"""
            font-weight: 700;
            color: {Colors.SECONDARY_TEXT};
            font-size: 11px;
            letter-spacing: 0.5px;
            background: transparent;
        """)
        left_layout.addWidget(title)
        
        components = [
            ("📝", "Title Block"),
            ("📊", "Sensorgram"),
            ("📈", "Fitting Plot"),
            ("📋", "Results Table"),
            ("📉", "Residuals"),
            ("📝", "Text Block"),
            ("🔬", "Methods"),
        ]
        
        for icon, name in components:
            btn = QPushButton(f"{icon} {name}")
            btn.setProperty("secondary", True)
            btn.setStyleSheet("text-align: left; padding-left: 12px;")
            left_layout.addWidget(btn)
        
        left_layout.addSpacing(20)
        
        templates_label = QLabel("TEMPLATES")
        templates_label.setStyleSheet(f"""
            font-weight: 700;
            color: {Colors.SECONDARY_TEXT};
            font-size: 11px;
            letter-spacing: 0.5px;
            background: transparent;
        """)
        left_layout.addWidget(templates_label)
        
        template_group = QButtonGroup(self)
        for i, name in enumerate(["Standard", "Detailed", "Summary", "Custom..."]):
            rb = QRadioButton(name)
            if i == 0:
                rb.setChecked(True)
            template_group.addButton(rb)
            left_layout.addWidget(rb)
        
        left_layout.addStretch()
        layout.addWidget(left_panel)
        
        # Center: Report preview
        preview_group = QGroupBox("Report Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        # Simulated report preview
        preview = QFrame()
        preview.setStyleSheet(f"""
            QFrame {{
                background: {Colors.BACKGROUND_WHITE};
                border: 1px solid {Colors.OVERLAY_LIGHT_10};
                border-radius: 8px;
            }}
        """)
        preview_inner = QVBoxLayout(preview)
        preview_inner.setContentsMargins(24, 24, 24, 24)
        
        # Report content
        report_title = QLabel("SPR Binding Analysis Report")
        report_title.setStyleSheet("font-size: 18px; font-weight: bold;")
        preview_inner.addWidget(report_title)
        
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"background: {Colors.OVERLAY_LIGHT_10}; max-height: 1px;")
        preview_inner.addWidget(line)
        
        preview_inner.addSpacing(12)
        
        meta_text = QLabel("Study: Anti-HER2 Binding Kinetics\nDate: February 2, 2026\nAnalyst: J. Smith")
        meta_text.setStyleSheet(f"color: {Colors.SECONDARY_TEXT}; background: transparent;")
        preview_inner.addWidget(meta_text)
        
        preview_inner.addSpacing(16)
        
        section1 = QLabel("1. Experimental Overview")
        section1.setStyleSheet("font-size: 14px; font-weight: 600;")
        preview_inner.addWidget(section1)
        
        fig_placeholder = QFrame()
        fig_placeholder.setFixedHeight(120)
        fig_placeholder.setStyleSheet(f"background: {Colors.BACKGROUND_LIGHT}; border: 1px dashed {Colors.OVERLAY_LIGHT_20}; border-radius: 6px;")
        fig_label = QLabel("📊 [Sensorgram Figure]")
        fig_label.setAlignment(Qt.AlignCenter)
        fig_layout = QVBoxLayout(fig_placeholder)
        fig_layout.addWidget(fig_label)
        preview_inner.addWidget(fig_placeholder)
        
        caption = QLabel("Figure 1: Overlay of sensorgrams at concentrations 6.25-100 nM.")
        caption.setStyleSheet(f"font-style: italic; color: {Colors.SECONDARY_TEXT}; font-size: 11px; background: transparent;")
        preview_inner.addWidget(caption)
        
        preview_inner.addSpacing(16)
        
        section2 = QLabel("2. Kinetic Analysis")
        section2.setStyleSheet("font-size: 14px; font-weight: 600;")
        preview_inner.addWidget(section2)
        
        result_text = QLabel("KD = 1.90 ± 0.15 nM")
        result_text.setStyleSheet("font-weight: 600; font-size: 16px;")
        preview_inner.addWidget(result_text)
        
        preview_inner.addStretch()
        
        preview_layout.addWidget(preview)
        
        # Page navigation
        page_nav = QHBoxLayout()
        page_nav.addStretch()
        page_nav.addWidget(QLabel("Page 1 of 3"))
        prev_btn = QPushButton("◀ Prev")
        prev_btn.setProperty("secondary", True)
        prev_btn.setFixedWidth(70)
        next_btn = QPushButton("Next ▶")
        next_btn.setProperty("secondary", True)
        next_btn.setFixedWidth(70)
        page_nav.addWidget(prev_btn)
        page_nav.addWidget(next_btn)
        preview_layout.addLayout(page_nav)
        
        layout.addWidget(preview_group, stretch=1)
        
        # Right: Output options
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_panel.setMaximumWidth(280)
        
        output_group = QGroupBox("Output Options")
        output_layout = QVBoxLayout(output_group)
        
        format_label = QLabel("Format:")
        format_label.setStyleSheet("font-weight: 600;")
        output_layout.addWidget(format_label)
        
        format_group = QButtonGroup(self)
        formats = [("● PDF", True), ("○ Word (.docx)", False), ("○ HTML", False), ("○ PowerPoint", False)]
        for text, checked in formats:
            rb = QRadioButton(text.replace("● ", "").replace("○ ", ""))
            rb.setChecked(checked)
            format_group.addButton(rb)
            output_layout.addWidget(rb)
        
        output_layout.addSpacing(12)
        
        page_label = QLabel("Page Size:")
        page_label.setStyleSheet("font-weight: 600;")
        output_layout.addWidget(page_label)
        
        page_combo = QComboBox()
        page_combo.addItems(["Letter (8.5x11\")", "A4", "Legal"])
        output_layout.addWidget(page_combo)
        
        output_layout.addSpacing(12)
        
        options_label = QLabel("Include:")
        options_label.setStyleSheet("font-weight: 600;")
        output_layout.addWidget(options_label)
        
        for text, checked in [
            ("Raw data appendix", True),
            ("Methods section", True),
            ("QC metrics", True),
            ("Analyst signature", False),
        ]:
            cb = QCheckBox(text)
            cb.setChecked(checked)
            output_layout.addWidget(cb)
        
        output_layout.addStretch()
        
        right_layout.addWidget(output_group)
        
        # Export buttons
        preview_btn = QPushButton("Preview Full Report")
        preview_btn.setProperty("secondary", True)
        right_layout.addWidget(preview_btn)
        
        export_btn = QPushButton("📄 Export Report")
        export_btn.setStyleSheet(f"""
            QPushButton {{
                background: {Colors.SUCCESS};
                color: white;
                font-weight: 600;
                padding: 12px;
            }}
            QPushButton:hover {{
                background: #2DB350;
            }}
        """)
        export_btn.clicked.connect(self._export_report)
        right_layout.addWidget(export_btn)
        
        right_layout.addStretch()
        layout.addWidget(right_panel)
    
    def _export_report(self):
        """Export report (demo)."""
        QMessageBox.information(
            self,
            "Export Report",
            "In the full version, this would export a PDF report.\n\n"
            "Report would include:\n"
            "• Title and metadata\n"
            "• Sensorgram figures\n"
            "• Fitting results table\n"
            "• Methods section"
        )


# ============================================================================
# MAIN WINDOW
# ============================================================================

class AnalyzeMainWindow(QMainWindow):
    """Main window for Affilabs.analyze."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Affilabs.analyze - SPR Data Analysis")
        self.setMinimumSize(1400, 900)
        self.resize(1600, 1000)
        
        # Initialize data storage for imported Affilabs.core files
        self.loaded_data = None
        
        self._setup_ui()
        self._setup_toolbar()
        self._setup_statusbar()
    
    def _setup_ui(self):
        """Setup the main UI layout."""
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Main splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        
        # Left panel - Project Explorer
        self.project_explorer = ProjectExplorer()
        self.project_explorer.setMinimumWidth(200)
        self.project_explorer.setMaximumWidth(300)
        splitter.addWidget(self.project_explorer)
        
        # Center - Tab widget
        self.tabs = QTabWidget()
        self.tabs.addTab(DataTab(), "Data")
        self.tabs.addTab(FittingTab(), "Fitting")
        self.tabs.addTab(ReportTab(), "Report")
        splitter.addWidget(self.tabs)
        
        # Right panel - Properties
        self.properties_panel = PropertiesPanel()
        self.properties_panel.setMinimumWidth(180)
        self.properties_panel.setMaximumWidth(250)
        splitter.addWidget(self.properties_panel)
        
        # Set splitter sizes
        splitter.setSizes([220, 1000, 200])
        
        main_layout.addWidget(splitter)
        
        # Connect tree selection to properties panel
        self.project_explorer.tree.itemClicked.connect(self._on_item_selected)
    
    def _setup_toolbar(self):
        """Setup the toolbar - matching Affilabs.core navigation bar style."""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setFixedHeight(60)
        toolbar.setStyleSheet(f"""
            QToolBar {{
                background: {Colors.BACKGROUND_WHITE};
                border-bottom: 1px solid {Colors.OVERLAY_LIGHT_10};
                padding: 8px 16px;
                spacing: 8px;
            }}
            QToolButton {{
                background: {Colors.OVERLAY_LIGHT_4};
                border: none;
                padding: 8px 16px;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 500;
                color: {Colors.PRIMARY_TEXT};
            }}
            QToolButton:hover {{
                background: {Colors.OVERLAY_LIGHT_8};
            }}
            QToolButton:pressed {{
                background: {Colors.OVERLAY_LIGHT_10};
            }}
        """)
        
        # File actions
        toolbar.addAction("📂 New")
        toolbar.addAction("📁 Open")
        toolbar.addAction("💾 Save")
        toolbar.addSeparator()
        
        # Import
        import_action = toolbar.addAction("📊 Import")
        import_action.triggered.connect(self._import_data)
        toolbar.addSeparator()
        
        # Analysis actions
        toolbar.addAction("▶ Fit")
        toolbar.addAction("📄 Report")
        toolbar.addSeparator()
        
        # Settings
        toolbar.addAction("⚙ Settings")
        
        self.addToolBar(toolbar)
    
    def _setup_statusbar(self):
        """Setup the status bar."""
        statusbar = QStatusBar()
        statusbar.showMessage("Ready")
        
        # Add permanent widgets
        statusbar.addPermanentWidget(QLabel("Project: Demo Project"))
        statusbar.addPermanentWidget(QLabel("5 runs loaded"))
        statusbar.addPermanentWidget(QLabel("Memory: 124 MB"))
        
        self.setStatusBar(statusbar)
    
    def _on_item_selected(self, item):
        """Handle tree item selection."""
        name = item.text(0).replace("📁 ", "").replace("📄 ", "")
        
        # Update properties panel
        if "nM" in name:
            props = {
                "Duration:": "6.7 min",
                "Points:": "4000",
                "Concentration:": name,
                "Analyte:": "Anti-HER2",
                "Fit Status:": "⏳ Pending",
            }
            self.properties_panel.set_selected(name, props)
        else:
            self.properties_panel.set_selected(name)
    
    def _import_data(self):
        """Import data from Affilabs.core Excel file.
        
        Reads the standard Affilabs.core export format with sheets:
        - Raw Data: Long format (channel, time, value, timestamp)
        - Channel Data: Wide format (Time A, Channel A, Time B, Channel B, etc.)
        - Cycles: Cycle definitions with timing and concentration
        - Flags: User-added markers
        - Events: Timestamped events
        - Analysis: Any analysis results
        - Metadata: Key-value pairs
        - Alignment: Edits tab settings
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Affilabs.core Data",
            "",
            "Excel Files (*.xlsx);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            self.statusBar().showMessage(f"Loading: {file_path}...")
            QApplication.processEvents()
            
            # Load all sheets from Excel file
            excel_data = pd.read_excel(file_path, sheet_name=None, engine="openpyxl")
            
            # Store loaded data
            self.loaded_data = {
                "filepath": file_path,
                "raw_data": excel_data.get("Raw Data", pd.DataFrame()),
                "channel_data": excel_data.get("Channel Data", pd.DataFrame()),
                "cycles": excel_data.get("Cycles", pd.DataFrame()),
                "flags": excel_data.get("Flags", pd.DataFrame()),
                "events": excel_data.get("Events", pd.DataFrame()),
                "analysis": excel_data.get("Analysis", pd.DataFrame()),
                "alignment": excel_data.get("Alignment", pd.DataFrame()),
                "metadata": {},
            }
            
            # Parse metadata from key-value format
            if "Metadata" in excel_data:
                meta_df = excel_data["Metadata"]
                if not meta_df.empty and "key" in meta_df.columns and "value" in meta_df.columns:
                    for _, row in meta_df.iterrows():
                        self.loaded_data["metadata"][row["key"]] = row["value"]
            
            # Update UI with loaded data
            self._populate_from_loaded_data()
            
            # Show success
            filename = Path(file_path).name
            n_cycles = len(self.loaded_data["cycles"])
            n_points = len(self.loaded_data["raw_data"])
            self.statusBar().showMessage(
                f"✓ Loaded: {filename} | {n_cycles} cycles | {n_points} data points"
            )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Import Error",
                f"Failed to import file:\n{e}\n\nMake sure this is an Affilabs.core export file."
            )
            self.statusBar().showMessage("Import failed")
    
    def _populate_from_loaded_data(self):
        """Populate UI components from loaded Affilabs.core data."""
        if not hasattr(self, 'loaded_data'):
            return
        
        data = self.loaded_data
        filepath = Path(data["filepath"])
        
        # === Update Project Explorer ===
        self.project_explorer.tree.clear()
        
        project_name = filepath.stem
        project = QTreeWidgetItem(self.project_explorer.tree, [f"📁 {project_name}"])
        project.setExpanded(True)
        
        # Add cycles as tree items
        cycles_df = data["cycles"]
        if not cycles_df.empty:
            # Group by cycle type if available
            if "type" in cycles_df.columns:
                cycle_types = cycles_df["type"].unique()
                for ctype in cycle_types:
                    type_item = QTreeWidgetItem(project, [f"📁 {ctype}"])
                    type_item.setExpanded(True)
                    
                    type_cycles = cycles_df[cycles_df["type"] == ctype]
                    for _, cycle in type_cycles.iterrows():
                        # Build cycle label
                        cycle_num = cycle.get("cycle_num", cycle.get("cycle_id", "?"))
                        conc = cycle.get("concentration_value", "")
                        units = cycle.get("concentration_units", cycle.get("units", ""))
                        name = cycle.get("name", "")
                        
                        if conc and units:
                            label = f"📄 Cycle {cycle_num}: {conc} {units}"
                        elif name:
                            label = f"📄 Cycle {cycle_num}: {name}"
                        else:
                            label = f"📄 Cycle {cycle_num}"
                        
                        QTreeWidgetItem(type_item, [label])
            else:
                # No type column, just list all cycles
                for _, cycle in cycles_df.iterrows():
                    cycle_num = cycle.get("cycle_num", cycle.get("cycle_id", "?"))
                    conc = cycle.get("concentration_value", "")
                    units = cycle.get("concentration_units", "")
                    
                    if conc:
                        label = f"📄 Cycle {cycle_num}: {conc} {units}"
                    else:
                        label = f"📄 Cycle {cycle_num}"
                    
                    QTreeWidgetItem(project, [label])
        
        # Update quick stats
        n_runs = len(cycles_df) if not cycles_df.empty else 0
        self.project_explorer.update_stats(n_runs, 0, "—")
        
        # === Update Data Tab Sensorgram Plot ===
        data_tab = self.tabs.widget(0)  # DataTab is first tab
        if hasattr(data_tab, 'plot'):
            data_tab.plot.clear_curves()
            
            channel_data = data["channel_data"]
            if not channel_data.empty:
                # Plot each channel from wide format
                colors = ["#0066CC", "#CC0000", "#009933", "#FF9900"]  # A=blue, B=red, C=green, D=orange
                
                for i, ch in enumerate(["A", "B", "C", "D"]):
                    time_col = f"Time {ch} (s)"
                    value_col = f"Channel {ch} (nm)"
                    
                    if time_col in channel_data.columns and value_col in channel_data.columns:
                        t = channel_data[time_col].dropna().values
                        R = channel_data[value_col].dropna().values
                        
                        if len(t) > 0 and len(R) > 0:
                            # Ensure same length
                            min_len = min(len(t), len(R))
                            data_tab.plot.add_curve(
                                t[:min_len], R[:min_len], 
                                f"Channel {ch}", colors[i]
                            )
        
        # === Update Data Tab Table ===
        if hasattr(data_tab, 'data_table') and not cycles_df.empty:
            data_tab.data_table.setRowCount(len(cycles_df))
            
            for row, (_, cycle) in enumerate(cycles_df.iterrows()):
                # Run name
                cycle_num = cycle.get("cycle_num", cycle.get("cycle_id", row + 1))
                data_tab.data_table.setItem(row, 0, QTableWidgetItem(f"☑ Cycle {cycle_num}"))
                
                # Concentration
                conc = cycle.get("concentration_value", "")
                units = cycle.get("concentration_units", cycle.get("units", ""))
                data_tab.data_table.setItem(row, 1, QTableWidgetItem(f"{conc} {units}" if conc else "—"))
                
                # Channel (from concentrations_formatted or default)
                ch = "A"  # Default
                if "concentrations_formatted" in cycle:
                    ch = cycle["concentrations_formatted"].split(":")[0] if cycle["concentrations_formatted"] else "A"
                data_tab.data_table.setItem(row, 2, QTableWidgetItem(ch))
                
                # Rmax (from delta_spr if available)
                rmax = cycle.get("delta_spr", "—")
                data_tab.data_table.setItem(row, 3, QTableWidgetItem(str(rmax) if rmax else "—"))
                
                # Status
                data_tab.data_table.setItem(row, 4, QTableWidgetItem("✓ Loaded"))
        
        # === Update Properties Panel with Metadata ===
        meta = data["metadata"]
        if meta:
            props = {}
            for key in ["experiment_name", "user", "date", "instrument", "chip_type"]:
                if key in meta:
                    props[f"{key.replace('_', ' ').title()}:"] = str(meta[key])
            
            if props:
                self.properties_panel.set_selected(filepath.stem, props)


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    
    window = AnalyzeMainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
