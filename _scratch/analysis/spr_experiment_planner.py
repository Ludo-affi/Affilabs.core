"""SPR Experiment Planner - Standalone UI Tool.

Interactive experiment design tool for Surface Plasmon Resonance.
Helps plan immobilization levels, estimate responses, and design concentration ranges.

Usage:
    python spr_experiment_planner.py
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit,
    QTableWidget, QTableWidgetItem, QTabWidget, QSpinBox, QDoubleSpinBox,
    QCheckBox, QSplitter, QMessageBox, QDialog, QListWidget, QListWidgetItem,
    QDialogButtonBox, QFileDialog, QMenu
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont, QColor, QPalette, QAction
import numpy as np

# Import our protein utility
from protein_utils import ProteinUtility


class UniProtLookupThread(QThread):
    """Background thread for UniProt API calls."""
    
    result_ready = Signal(dict)
    error_occurred = Signal(str)
    
    def __init__(self, uniprot_id: str):
        super().__init__()
        self.uniprot_id = uniprot_id
        self.util = ProteinUtility()
    
    def run(self):
        """Fetch protein data in background."""
        try:
            data = self.util.fetch_uniprot_data(self.uniprot_id)
            if data:
                self.result_ready.emit(data)
            else:
                self.error_occurred.emit(f"UniProt ID '{self.uniprot_id}' not found")
        except Exception as e:
            self.error_occurred.emit(str(e))


class UniProtSearchThread(QThread):
    """Background thread for UniProt search."""
    
    results_ready = Signal(list)
    error_occurred = Signal(str)
    
    def __init__(self, protein_name: str, organism: str = "human"):
        super().__init__()
        self.protein_name = protein_name
        self.organism = organism
        self.util = ProteinUtility()
    
    def run(self):
        """Search UniProt in background."""
        try:
            results = self.util.search_uniprot_by_name(self.protein_name, self.organism)
            if results:
                self.results_ready.emit(results)
            else:
                self.error_occurred.emit(f"No results found for '{self.protein_name}'")
        except Exception as e:
            self.error_occurred.emit(str(e))


class ProteinSearchDialog(QDialog):
    """Dialog for searching and selecting proteins from UniProt."""
    
    protein_selected = Signal(str)  # Emits UniProt ID
    
    def __init__(self, parent=None, protein_type: str = "protein"):
        super().__init__(parent)
        self.protein_type = protein_type
        self.search_results = []
        self.init_ui()
    
    def init_ui(self):
        """Initialize search dialog UI."""
        self.setWindowTitle(f"Search {self.protein_type.title()}")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        
        layout = QVBoxLayout(self)
        
        # Search input
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Protein Name:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("e.g., TNF alpha, IgG, Insulin")
        self.search_input.returnPressed.connect(self.perform_search)
        search_layout.addWidget(self.search_input)
        
        search_layout.addWidget(QLabel("Organism:"))
        self.organism_combo = QComboBox()
        self.organism_combo.addItems(["human", "mouse", "rat", "bovine", "rabbit"])
        search_layout.addWidget(self.organism_combo)
        
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self.perform_search)
        search_layout.addWidget(self.search_btn)
        
        layout.addLayout(search_layout)
        
        # Status label
        self.status_label = QLabel("Enter protein name and click Search")
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.status_label)
        
        # Results list
        self.results_list = QListWidget()
        self.results_list.itemDoubleClicked.connect(self.select_protein)
        layout.addWidget(self.results_list)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.select_protein)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def perform_search(self):
        """Execute UniProt search."""
        protein_name = self.search_input.text().strip()
        if not protein_name:
            self.status_label.setText("⚠️ Enter a protein name")
            return
        
        organism = self.organism_combo.currentText()
        self.status_label.setText(f"🔄 Searching for '{protein_name}' in {organism}...")
        self.results_list.clear()
        self.search_btn.setEnabled(False)
        
        # Start search thread
        self.search_thread = UniProtSearchThread(protein_name, organism)
        self.search_thread.results_ready.connect(self.on_search_results)
        self.search_thread.error_occurred.connect(self.on_search_error)
        self.search_thread.start()
    
    def on_search_results(self, results: list):
        """Handle search results."""
        self.search_results = results
        self.results_list.clear()
        
        for result in results:
            accession = result['accession']
            name = result['name']
            mw_kda = result['mw_da'] / 1000 if result['mw_da'] else 0
            
            text = f"{accession} - {name} ({mw_kda:.1f} kDa)"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, accession)
            self.results_list.addItem(item)
        
        self.status_label.setText(f"✓ Found {len(results)} results")
        self.search_btn.setEnabled(True)
    
    def on_search_error(self, error: str):
        """Handle search error."""
        self.status_label.setText(f"❌ {error}")
        self.search_btn.setEnabled(True)
    
    def select_protein(self):
        """Select protein and close dialog."""
        current_item = self.results_list.currentItem()
        if current_item:
            uniprot_id = current_item.data(Qt.ItemDataRole.UserRole)
            self.protein_selected.emit(uniprot_id)
            self.accept()
        else:
            self.status_label.setText("⚠️ Select a protein from the list")


class SPRCalculator:
    """Core calculations for SPR experiment planning."""
    
    @staticmethod
    def calculate_theoretical_rmax(
        mw_analyte_da: float,
        mw_ligand_da: float,
        r_ligand_ru: float,
        stoichiometry: int = 1
    ) -> float:
        """Calculate theoretical maximum response.
        
        Args:
            mw_analyte_da: Molecular weight of analyte (flowing, in Daltons)
            mw_ligand_da: Molecular weight of immobilized ligand (in Daltons)
            r_ligand_ru: Immobilization level of ligand (RU)
            stoichiometry: Binding sites per ligand (default: 1 for 1:1)
        
        Returns:
            Theoretical Rmax in RU
        """
        return (mw_analyte_da / mw_ligand_da) * r_ligand_ru * stoichiometry
    
    @staticmethod
    def calculate_surface_activity(rmax_experimental: float, rmax_theoretical: float) -> float:
        """Calculate percentage of active binding sites.
        
        Args:
            rmax_experimental: Observed Rmax from experiment
            rmax_theoretical: Calculated theoretical Rmax
        
        Returns:
            Activity percentage (typically 50-110%)
        """
        return (rmax_experimental / rmax_theoretical) * 100
    
    @staticmethod
    def calculate_expected_response(
        concentration_m: float,
        kd_m: float,
        rmax_ru: float
    ) -> float:
        """Calculate expected equilibrium response at given concentration.
        
        Uses steady-state Langmuir equation:
        Req = Rmax × C / (C + KD)
        
        Args:
            concentration_m: Analyte concentration (M)
            kd_m: Equilibrium dissociation constant (M)
            rmax_ru: Maximum response (RU)
        
        Returns:
            Expected response (RU)
        """
        return rmax_ru * concentration_m / (concentration_m + kd_m)
    
    @staticmethod
    def suggest_concentration_range(kd_m: float, num_points: int = 5) -> list:
        """Suggest concentration series for kinetic analysis.
        
        Rule of thumb: 0.1×KD to 10×KD with logarithmic spacing
        
        Args:
            kd_m: Estimated KD in Molarity
            num_points: Number of concentrations (default: 5)
        
        Returns:
            List of concentrations in Molarity
        """
        # 0.1 KD to 10 KD, logarithmic spacing
        log_min = np.log10(kd_m * 0.1)
        log_max = np.log10(kd_m * 10)
        log_concentrations = np.linspace(log_min, log_max, num_points)
        return [10**x for x in log_concentrations]
    
    @staticmethod
    def calculate_required_immobilization(
        mw_analyte_da: float,
        mw_ligand_da: float,
        desired_rmax_ru: float,
        stoichiometry: int = 1
    ) -> float:
        """Calculate required ligand immobilization level.
        
        Inverse of theoretical Rmax calculation.
        
        Args:
            mw_analyte_da: Analyte MW
            mw_ligand_da: Ligand MW
            desired_rmax_ru: Target Rmax
            stoichiometry: Binding sites
        
        Returns:
            Required ligand immobilization (RU)
        """
        return desired_rmax_ru * mw_ligand_da / (mw_analyte_da * stoichiometry)


class ExperimentPlannerUI(QMainWindow):
    """Main UI for SPR Experiment Planner."""
    
    def __init__(self):
        super().__init__()
        self.protein_util = ProteinUtility()
        self.calc = SPRCalculator()
        
        # Stored protein data
        self.ligand_data: Optional[Dict] = None
        self.analyte_data: Optional[Dict] = None
        
        # Custom protein library
        self.custom_proteins_file = Path.home() / '.spr_planner' / 'custom_proteins.json'
        self.custom_proteins = self._load_custom_proteins()
        
        # Experiment plans
        self.experiments_dir = Path.home() / '.spr_planner' / 'experiments'
        self.experiments_dir.mkdir(parents=True, exist_ok=True)
        
        # Current experiment data
        self.current_experiment_file: Optional[Path] = None
        
        self.init_ui()
        self._create_menu_bar()
        self.setStyleSheet(self._get_stylesheet())
    
    def _create_menu_bar(self):
        """Create menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        new_action = QAction("New Experiment", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._new_experiment)
        file_menu.addAction(new_action)
        
        open_action = QAction("Open Experiment...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_experiment)
        file_menu.addAction(open_action)
        
        save_action = QAction("Save Experiment", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_experiment)
        file_menu.addAction(save_action)
        
        save_as_action = QAction("Save Experiment As...", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self._save_experiment_as)
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        export_action = QAction("Export Report...", self)
        export_action.triggered.connect(self._export_report)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Proteins menu
        proteins_menu = menubar.addMenu("Proteins")
        
        add_custom_action = QAction("Add Custom Protein...", self)
        add_custom_action.triggered.connect(self._add_custom_protein)
        proteins_menu.addAction(add_custom_action)
        
        view_custom_action = QAction("View Custom Proteins...", self)
        view_custom_action.triggered.connect(self._view_custom_proteins)
        proteins_menu.addAction(view_custom_action)
        
        proteins_menu.addSeparator()
        
        import_proteins_action = QAction("Import Protein Library...", self)
        import_proteins_action.triggered.connect(self._import_protein_library)
        proteins_menu.addAction(import_proteins_action)
        
        export_proteins_action = QAction("Export Protein Library...", self)
        export_proteins_action.triggered.connect(self._export_protein_library)
        proteins_menu.addAction(export_proteins_action)
    
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("SPR Experiment Planner - AffiLabs.core")
        self.setGeometry(100, 100, 1200, 800)
        self.ligand_custom_btn = QPushButton("Load Custom")
        self.ligand_custom_btn.clicked.connect(lambda: self._load_custom_protein('ligand'))
        ligand_lookup_layout.addWidget(self.ligand_custom_btn)
        
        self.current_experiment_file: Optional[Path] = None
        
        self.init_ui()
        self._create_menu_bar()
        self.setStyleSheet(self._get_stylesheet())
    
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("SPR Experiment Planner - AffiLabs.core")
        self.setGeometry(100, 100, 1200, 800)
        
        # Central widget with tabs
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Create tab widget
        tabs = QTabWidget()
        
        # Tab 1: Protein Setup
        tabs.addTab(self._create_protein_setup_tab(), "1. Protein Setup")
        
        # Tab 2: Immobilization Planning
        tabs.addTab(self._create_immobilization_tab(), "2. Immobilization")
        
        # Tab 3: Concentration Series Design
        tabs.addTab(self._create_concentration_tab(), "3. Concentration Series")
        
        # Tab 4: Validation & Analysis
        tabs.addTab(self._create_validation_tab(), "4. Validation")
        
        # Tab 5: Unit Converter
        tabs.addTab(self._create_converter_tab(), "5. Unit Converter")
        
        layout.addWidget(tabs)
    
    def _create_protein_setup_tab(self) -> QWidget:
        """Create protein setup tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Ligand (immobilized) section
        ligand_group = QGroupBox("Ligand (Immobilized on Surface)")
        ligand_layout = QVBoxLayout(ligand_group)
        
        # Ligand UniProt lookup
        ligand_lookup_layout = QHBoxLayout()
        ligand_lookup_layout.addWidget(QLabel("UniProt ID:"))
        self.ligand_uniprot_input = QLineEdit()
        self.ligand_uniprot_input.setPlaceholderText("e.g., P01375 or search by name")
        ligand_lookup_layout.addWidget(self.ligand_uniprot_input)
        
        self.ligand_lookup_btn = QPushButton("Lookup")
        self.ligand_lookup_btn.clicked.connect(lambda: self._lookup_protein('ligand'))
        ligand_lookup_layout.addWidget(self.ligand_lookup_btn)
        
        self.ligand_search_btn = QPushButton("Search by Name")
        self.ligand_search_btn.clicked.connect(lambda: self._search_protein('ligand'))
        ligand_lookup_layout.addWidget(self.ligand_search_btn)
        
        ligand_layout.addLayout(ligand_lookup_layout)
        
        # Ligand manual entry
        ligand_manual_layout = QHBoxLayout()
        ligand_manual_layout.addWidget(QLabel("Name:"))
        self.ligand_name_input = QLineEdit()
        self.ligand_name_input.setPlaceholderText("Protein name")
        ligand_manual_layout.addWidget(self.ligand_name_input)
        
        ligand_manual_layout.addWidget(QLabel("MW (kDa):"))
        self.ligand_mw_input = QDoubleSpinBox()
        self.ligand_mw_input.setRange(1, 1000)
        self.ligand_mw_input.setValue(150.0)
        self.ligand_mw_input.setSuffix(" kDa")
        ligand_manual_layout.addWidget(self.ligand_mw_input)
        
        ligand_layout.addLayout(ligand_manual_layout)
        
        # Ligand info display
        self.ligand_info_label = QLabel("No ligand loaded")
        self.ligand_info_label.setStyleSheet("color: #666; font-style: italic;")
        ligand_layout.addWidget(self.ligand_info_label)
        
        layout.addWidget(ligand_group)
        
        # Analyte (flowing) section
        analyte_group = QGroupBox("Analyte (Flowing in Solution)")
        analyte_layout = QVBoxLayout(analyte_group)
        
        # Analyte UniProt lookup
        analyte_lookup_layout = QHBoxLayout()
        analyte_lookup_layout.addWidget(QLabel("UniProt ID:"))
        self.analyte_uniprot_input = QLineEdit()
        self.analyte_uniprot_input.setPlaceholderText("e.g., P12345")
        analyte_lookup_layout.addWidget(self.analyte_uniprot_input)
        
        self.analyte_lookup_btn = QPushButton("Lookup")
        self.analyte_lookup_btn.clicked.connect(lambda: self._lookup_protein('analyte'))
        analyte_lookup_layout.addWidget(self.analyte_lookup_btn)
        
        self.analyte_custom_btn = QPushButton("Load Custom")
        self.analyte_custom_btn.clicked.connect(lambda: self._load_custom_protein('analyte'))
        analyte_lookup_layout.addWidget(self.analyte_custom_btn)
        
        self.analyte_search_btn = QPushButton("Search by Name")
        self.analyte_search_btn.clicked.connect(lambda: self._search_protein('analyte'))
        analyte_lookup_layout.addWidget(self.analyte_search_btn)
        
        analyte_layout.addLayout(analyte_lookup_layout)
        
        # Analyte manual entry
        analyte_manual_layout = QHBoxLayout()
        analyte_manual_layout.addWidget(QLabel("Name:"))
        self.analyte_name_input = QLineEdit()
        self.analyte_name_input.setPlaceholderText("Protein name")
        analyte_manual_layout.addWidget(self.analyte_name_input)
        
        analyte_manual_layout.addWidget(QLabel("MW (kDa):"))
        self.analyte_mw_input = QDoubleSpinBox()
        self.analyte_mw_input.setRange(1, 1000)
        self.analyte_mw_input.setValue(50.0)
        self.analyte_mw_input.setSuffix(" kDa")
        analyte_manual_layout.addWidget(self.analyte_mw_input)
        
        analyte_layout.addLayout(analyte_manual_layout)
        
        # Analyte info display
        self.analyte_info_label = QLabel("No analyte loaded")
        self.analyte_info_label.setStyleSheet("color: #666; font-style: italic;")
        analyte_layout.addWidget(self.analyte_info_label)
        
        layout.addWidget(analyte_group)
        
        # Binding parameters
        binding_group = QGroupBox("Binding Parameters")
        binding_layout = QHBoxLayout(binding_group)
        
        binding_layout.addWidget(QLabel("Stoichiometry:"))
        self.stoichiometry_input = QSpinBox()
        self.stoichiometry_input.setRange(1, 10)
        self.stoichiometry_input.setValue(1)
        self.stoichiometry_input.setToolTip("Number of analyte molecules per ligand (1:1, 2:1, etc.)")
        binding_layout.addWidget(self.stoichiometry_input)
        
        binding_layout.addWidget(QLabel("Estimated KD:"))
        self.kd_value_input = QDoubleSpinBox()
        self.kd_value_input.setRange(0.001, 10000)
        self.kd_value_input.setValue(10.0)
        self.kd_value_input.setDecimals(3)
        binding_layout.addWidget(self.kd_value_input)
        
        self.kd_unit_combo = QComboBox()
        self.kd_unit_combo.addItems(["nM", "µM", "mM", "M"])
        self.kd_unit_combo.setCurrentText("nM")
        binding_layout.addWidget(self.kd_unit_combo)
        
        binding_layout.addStretch()
        
        layout.addWidget(binding_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_immobilization_tab(self) -> QWidget:
        """Create immobilization planning tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Target Rmax approach
        target_group = QGroupBox("Design from Target Rmax")
        target_layout = QVBoxLayout(target_group)
        
        target_input_layout = QHBoxLayout()
        target_input_layout.addWidget(QLabel("Desired Rmax:"))
        self.target_rmax_input = QDoubleSpinBox()
        self.target_rmax_input.setRange(10, 10000)
        self.target_rmax_input.setValue(500)
        self.target_rmax_input.setSuffix(" RU")
        target_input_layout.addWidget(self.target_rmax_input)
        
        calc_immob_btn = QPushButton("Calculate Required Immobilization")
        calc_immob_btn.clicked.connect(self._calculate_required_immobilization)
        target_input_layout.addWidget(calc_immob_btn)
        
        target_input_layout.addStretch()
        target_layout.addLayout(target_input_layout)
        
        self.required_immob_label = QLabel("")
        self.required_immob_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #007AFF;")
        target_layout.addWidget(self.required_immob_label)
        
        layout.addWidget(target_group)
        
        # Immobilization level approach
        immob_group = QGroupBox("Design from Immobilization Level")
        immob_layout = QVBoxLayout(immob_group)
        
        immob_input_layout = QHBoxLayout()
        immob_input_layout.addWidget(QLabel("Ligand Immobilization:"))
        self.immob_level_input = QDoubleSpinBox()
        self.immob_level_input.setRange(10, 20000)
        self.immob_level_input.setValue(1000)
        self.immob_level_input.setSuffix(" RU")
        immob_input_layout.addWidget(self.immob_level_input)
        
        calc_rmax_btn = QPushButton("Calculate Theoretical Rmax")
        calc_rmax_btn.clicked.connect(self._calculate_theoretical_rmax)
        immob_input_layout.addWidget(calc_rmax_btn)
        
        immob_input_layout.addStretch()
        immob_layout.addLayout(immob_input_layout)
        
        self.theoretical_rmax_label = QLabel("")
        self.theoretical_rmax_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #34C759;")
        immob_layout.addWidget(self.theoretical_rmax_label)
        
        layout.addWidget(immob_group)
        
        # Recommendations
        rec_group = QGroupBox("Immobilization Recommendations")
        rec_layout = QVBoxLayout(rec_group)
        
        self.immob_recommendations = QTextEdit()
        self.immob_recommendations.setReadOnly(True)
        self.immob_recommendations.setMaximumHeight(200)
        self.immob_recommendations.setStyleSheet("background: #F5F5F7; border: 1px solid #D1D1D6;")
        rec_layout.addWidget(self.immob_recommendations)
        
        layout.addWidget(rec_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_concentration_tab(self) -> QWidget:
        """Create concentration series design tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Design parameters
        design_group = QGroupBox("Concentration Series Design")
        design_layout = QVBoxLayout(design_group)
        
        # Number of concentrations
        num_conc_layout = QHBoxLayout()
        num_conc_layout.addWidget(QLabel("Number of concentrations:"))
        self.num_concentrations_input = QSpinBox()
        self.num_concentrations_input.setRange(3, 12)
        self.num_concentrations_input.setValue(5)
        num_conc_layout.addWidget(self.num_concentrations_input)
        num_conc_layout.addStretch()
        design_layout.addLayout(num_conc_layout)
        
        # Generate button
        generate_btn = QPushButton("Generate Concentration Series")
        generate_btn.clicked.connect(self._generate_concentration_series)
        design_layout.addWidget(generate_btn)
        
        layout.addWidget(design_group)
        
        # Concentration table
        table_group = QGroupBox("Planned Concentrations")
        table_layout = QVBoxLayout(table_group)
        
        self.concentration_table = QTableWidget()
        self.concentration_table.setColumnCount(5)
        self.concentration_table.setHorizontalHeaderLabels([
            "Concentration (nM)",
            "Concentration (µg/mL)",
            "C / KD Ratio",
            "Expected Response (RU)",
            "% Rmax"
        ])
        self.concentration_table.horizontalHeader().setStretchLastSection(True)
        table_layout.addWidget(self.concentration_table)
        
        layout.addWidget(table_group)
        
        # Export button
        export_layout = QHBoxLayout()
        export_btn = QPushButton("Export to Clipboard")
        export_btn.clicked.connect(self._export_concentration_table)
        export_layout.addWidget(export_btn)
        export_layout.addStretch()
        layout.addLayout(export_layout)
        
        return widget
    
    def _create_validation_tab(self) -> QWidget:
        """Create experimental validation tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Experimental data input
        exp_group = QGroupBox("Experimental Data")
        exp_layout = QVBoxLayout(exp_group)
        
        exp_input_layout = QHBoxLayout()
        exp_input_layout.addWidget(QLabel("Measured Rmax:"))
        self.measured_rmax_input = QDoubleSpinBox()
        self.measured_rmax_input.setRange(0, 20000)
        self.measured_rmax_input.setValue(0)
        self.measured_rmax_input.setSuffix(" RU")
        exp_input_layout.addWidget(self.measured_rmax_input)
        
        exp_input_layout.addWidget(QLabel("Actual Immobilization:"))
        self.measured_immob_input = QDoubleSpinBox()
        self.measured_immob_input.setRange(0, 20000)
        self.measured_immob_input.setValue(0)
        self.measured_immob_input.setSuffix(" RU")
        exp_input_layout.addWidget(self.measured_immob_input)
        
        validate_btn = QPushButton("Calculate Activity")
        validate_btn.clicked.connect(self._validate_experimental)
        exp_input_layout.addWidget(validate_btn)
        
        exp_input_layout.addStretch()
        exp_layout.addLayout(exp_input_layout)
        
        layout.addWidget(exp_group)
        
        # Validation results
        results_group = QGroupBox("Validation Results")
        results_layout = QVBoxLayout(results_group)
        
        self.validation_results = QTextEdit()
        self.validation_results.setReadOnly(True)
        self.validation_results.setStyleSheet("background: #F5F5F7; border: 1px solid #D1D1D6; font-family: 'Consolas', monospace;")
        results_layout.addWidget(self.validation_results)
        
        layout.addWidget(results_group)
        
        return widget
    
    def _lookup_protein(self, protein_type: str):
        """Lookup protein from UniProt."""
        if protein_type == 'ligand':
            uniprot_id = self.ligand_uniprot_input.text().strip()
            info_label = self.ligand_info_label
        else:
            uniprot_id = self.analyte_uniprot_input.text().strip()
            info_label = self.analyte_info_label
        
        if not uniprot_id:
            info_label.setText("⚠️ Enter UniProt ID")
            return
        
        info_label.setText("🔄 Fetching from UniProt...")
        
        # Start background thread
        thread = UniProtLookupThread(uniprot_id)
        thread.result_ready.connect(lambda data: self._on_protein_loaded(data, protein_type))
        thread.error_occurred.connect(lambda err: info_label.setText(f"❌ {err}"))
        thread.start()
        
        # Store thread reference to prevent garbage collection
        if protein_type == 'ligand':
            self._ligand_thread = thread
        else:
            self._analyte_thread = thread
    
    def _search_protein(self, protein_type: str):
        """Search protein by name using search dialog."""
        dialog = ProteinSearchDialog(self, protein_type)
        
        # Connect selection to lookup
        if protein_type == 'ligand':
            dialog.protein_selected.connect(self._on_ligand_search_selected)
        else:
            dialog.protein_selected.connect(self._on_analyte_search_selected)
        
        dialog.exec()
    
    def _on_ligand_search_selected(self, uniprot_id: str):
        """Handle ligand selection from search."""
        self.ligand_uniprot_input.setText(uniprot_id)
        self._lookup_protein('ligand')
    
    def _on_analyte_search_selected(self, uniprot_id: str):
        """Handle analyte selection from search."""
        self.analyte_uniprot_input.setText(uniprot_id)
        self._lookup_protein('analyte')
    
    def _on_protein_loaded(self, data: Dict, protein_type: str):
        """Handle protein data loaded from UniProt."""
        if protein_type == 'ligand':
            self.ligand_data = data
            self.ligand_name_input.setText(data['name'])
            self.ligand_mw_input.setValue(data['mw_da'] / 1000)  # Convert Da to kDa
            
            info_text = (f"✓ {data['name']}\n"
                        f"  {data['organism']}, {data['sequence_length']} aa, "
                        f"{data['mw_da']/1000:.1f} kDa")
            self.ligand_info_label.setText(info_text)
        else:
            self.analyte_data = data
            self.analyte_name_input.setText(data['name'])
            self.analyte_mw_input.setValue(data['mw_da'] / 1000)
            
            info_text = (f"✓ {data['name']}\n"
                        f"  {data['organism']}, {data['sequence_length']} aa, "
                        f"{data['mw_da']/1000:.1f} kDa")
            self.analyte_info_label.setText(info_text)
    
    def _calculate_required_immobilization(self):
        """Calculate required ligand immobilization for target Rmax."""
        mw_analyte = self.analyte_mw_input.value() * 1000  # kDa to Da
        mw_ligand = self.ligand_mw_input.value() * 1000
        target_rmax = self.target_rmax_input.value()
        stoichiometry = self.stoichiometry_input.value()
        
        required_immob = self.calc.calculate_required_immobilization(
            mw_analyte, mw_ligand, target_rmax, stoichiometry
        )
        
        self.required_immob_label.setText(
            f"✓ Required Ligand Immobilization: {required_immob:.0f} RU"
        )
        
        # Update recommendations
        self._update_immobilization_recommendations(required_immob, target_rmax)
    
    def _calculate_theoretical_rmax(self):
        """Calculate theoretical Rmax from immobilization level."""
        mw_analyte = self.analyte_mw_input.value() * 1000  # kDa to Da
        mw_ligand = self.ligand_mw_input.value() * 1000
        immob_level = self.immob_level_input.value()
        stoichiometry = self.stoichiometry_input.value()
        
        theoretical_rmax = self.calc.calculate_theoretical_rmax(
            mw_analyte, mw_ligand, immob_level, stoichiometry
        )
        
        self.theoretical_rmax_label.setText(
            f"✓ Theoretical Rmax: {theoretical_rmax:.0f} RU"
        )
        
        # Update recommendations
        self._update_immobilization_recommendations(immob_level, theoretical_rmax)
    
    def _update_immobilization_recommendations(self, immob_ru: float, rmax_ru: float):
        """Update immobilization recommendations text."""
        ligand_name = self.ligand_name_input.text() or "Ligand"
        analyte_name = self.analyte_name_input.text() or "Analyte"
        
        recommendations = []
        recommendations.append("═" * 70)
        recommendations.append("IMMOBILIZATION RECOMMENDATIONS")
        recommendations.append("═" * 70)
        recommendations.append("")
        
        recommendations.append(f"Ligand ({ligand_name}): {immob_ru:.0f} RU")
        recommendations.append(f"Expected Rmax ({analyte_name}): {rmax_ru:.0f} RU")
        recommendations.append("")
        
        # Guidelines
        recommendations.append("GUIDELINES:")
        recommendations.append("")
        
        if rmax_ru < 50:
            recommendations.append("⚠️  Low Rmax (<50 RU)")
            recommendations.append("   - May have poor signal-to-noise")
            recommendations.append("   - Consider increasing immobilization")
        elif rmax_ru > 1000:
            recommendations.append("⚠️  High Rmax (>1000 RU)")
            recommendations.append("   - Risk of mass transport limitations")
            recommendations.append("   - Consider reducing immobilization")
        else:
            recommendations.append("✓  Rmax is in optimal range (50-1000 RU)")
        
        recommendations.append("")
        recommendations.append("TYPICAL RANGES:")
        recommendations.append("  • Small molecules: 20-100 RU")
        recommendations.append("  • Proteins: 50-500 RU")
        recommendations.append("  • Large complexes: 200-1000 RU")
        recommendations.append("")
        
        # Mass transport check
        recommendations.append("MASS TRANSPORT CHECK:")
        if rmax_ru > 500:
            recommendations.append("  ⚠️  High Rmax may cause mass transport issues")
            recommendations.append("     Increase flow rate or reduce immobilization")
        else:
            recommendations.append("  ✓  Mass transport should be minimal")
        
        self.immob_recommendations.setText("\n".join(recommendations))
    
    def _generate_concentration_series(self):
        """Generate concentration series based on KD."""
        # Get KD in Molarity
        kd_value = self.kd_value_input.value()
        kd_unit = self.kd_unit_combo.currentText()
        
        unit_factors = {'nM': 1e-9, 'µM': 1e-6, 'mM': 1e-3, 'M': 1.0}
        kd_m = kd_value * unit_factors[kd_unit]
        
        # Get number of points
        num_points = self.num_concentrations_input.value()
        
        # Generate series
        concentrations_m = self.calc.suggest_concentration_range(kd_m, num_points)
        
        # Get Rmax for response calculation
        immob_level = self.immob_level_input.value()
        mw_analyte = self.analyte_mw_input.value() * 1000
        mw_ligand = self.ligand_mw_input.value() * 1000
        stoichiometry = self.stoichiometry_input.value()
        
        rmax = self.calc.calculate_theoretical_rmax(
            mw_analyte, mw_ligand, immob_level, stoichiometry
        )
        
        # Populate table
        self.concentration_table.setRowCount(num_points)
        
        for i, conc_m in enumerate(concentrations_m):
            # Concentration in nM
            conc_nm = conc_m * 1e9
            item_nm = QTableWidgetItem(f"{conc_nm:.2f}")
            self.concentration_table.setItem(i, 0, item_nm)
            
            # Concentration in µg/mL
            mw_analyte_da = mw_analyte
            conc_ug_ml = (conc_m * mw_analyte_da)  # M to g/L, then to µg/mL
            item_ug = QTableWidgetItem(f"{conc_ug_ml:.3f}")
            self.concentration_table.setItem(i, 1, item_ug)
            
            # C/KD ratio
            ratio = conc_m / kd_m
            item_ratio = QTableWidgetItem(f"{ratio:.2f}")
            self.concentration_table.setItem(i, 2, item_ratio)
            
            # Expected response
            response = self.calc.calculate_expected_response(conc_m, kd_m, rmax)
            item_response = QTableWidgetItem(f"{response:.1f}")
            self.concentration_table.setItem(i, 3, item_response)
            
            # % Rmax
            pct_rmax = (response / rmax) * 100
            item_pct = QTableWidgetItem(f"{pct_rmax:.1f}%")
            self.concentration_table.setItem(i, 4, item_pct)
            
            # Color code by saturation
            if pct_rmax < 10:
                color = QColor(255, 59, 48)  # Red - too low
            elif pct_rmax > 90:
                color = QColor(255, 149, 0)  # Orange - near saturation
            else:
                color = QColor(52, 199, 89)  # Green - good range
            
            for col in range(5):
                if self.concentration_table.item(i, col):
                    self.concentration_table.item(i, col).setBackground(color.lighter(160))
    
    def _export_concentration_table(self):
        """Export concentration table to clipboard."""
        from PySide6.QtWidgets import QApplication
        
        rows = self.concentration_table.rowCount()
        cols = self.concentration_table.columnCount()
        
        # Build TSV text
        lines = []
        
        # Header
        headers = [self.concentration_table.horizontalHeaderItem(i).text() 
                  for i in range(cols)]
        lines.append("\t".join(headers))
        
        # Data rows
        for row in range(rows):
            row_data = []
            for col in range(cols):
                item = self.concentration_table.item(row, col)
                row_data.append(item.text() if item else "")
            lines.append("\t".join(row_data))
        
        # Copy to clipboard
        clipboard = QApplication.clipboard()
        clipboard.setText("\n".join(lines))
        
        QMessageBox.information(self, "Exported", "Concentration table copied to clipboard!")
    
    def _validate_experimental(self):
        """Validate experimental results against theoretical."""
        measured_rmax = self.measured_rmax_input.value()
        measured_immob = self.measured_immob_input.value()
        
        if measured_rmax == 0 or measured_immob == 0:
            self.validation_results.setText("⚠️ Enter experimental data")
            return
        
        # Calculate theoretical Rmax
        mw_analyte = self.analyte_mw_input.value() * 1000
        mw_ligand = self.ligand_mw_input.value() * 1000
        stoichiometry = self.stoichiometry_input.value()
        
        theoretical_rmax = self.calc.calculate_theoretical_rmax(
            mw_analyte, mw_ligand, measured_immob, stoichiometry
        )
        
        # Calculate activity
        activity = self.calc.calculate_surface_activity(measured_rmax, theoretical_rmax)
        
        # Build results
        results = []
        results.append("═" * 70)
        results.append("VALIDATION RESULTS")
        results.append("═" * 70)
        results.append("")
        
        results.append(f"Measured Immobilization:    {measured_immob:.0f} RU")
        results.append(f"Theoretical Rmax:           {theoretical_rmax:.0f} RU")
        results.append(f"Experimental Rmax:          {measured_rmax:.0f} RU")
        results.append("")
        results.append(f"Surface Activity:           {activity:.1f}%")
        results.append("")
        
        # Interpretation
        results.append("INTERPRETATION:")
        results.append("")
        
        if 80 <= activity <= 110:
            results.append("✓ EXCELLENT - Activity within expected range")
            results.append("  Surface is highly functional")
        elif 50 <= activity < 80:
            results.append("⚠️  MODERATE - Lower than expected activity")
            results.append("  Possible causes:")
            results.append("    • Partial denaturation during immobilization")
            results.append("    • Steric hindrance")
            results.append("    • Orientation issues")
        elif 110 < activity <= 150:
            results.append("⚠️  HIGH - Activity above 100%")
            results.append("  Possible causes:")
            results.append("    • Avidity effects (multivalent binding)")
            results.append("    • Non-specific binding")
            results.append("    • Overestimated ligand MW")
        elif activity < 50:
            results.append("❌ LOW - Significantly reduced activity")
            results.append("  Possible causes:")
            results.append("    • Protein denaturation")
            results.append("    • Wrong orientation")
            results.append("    • Surface degradation")
        else:
            results.append("❌ VERY HIGH - Activity >150%")
            results.append("  Check experimental setup:")
            results.append("    • Verify MW values")
            results.append("    • Check for aggregation")
            results.append("    • Confirm stoichiometry")
        
        results.append("")
        results.append("TYPICAL ACTIVITY RANGES:")
        results.append("  • Direct amine coupling: 50-90%")
        results.append("  • Antibody capture:      80-100%")
        results.append("  • His-tag capture:       70-95%")
        
        self.validation_results.setText("\n".join(results))
    
    def _create_converter_tab(self) -> QWidget:
        """Create unit converter tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Converter group
        converter_group = QGroupBox("Concentration Unit Converter")
        converter_layout = QVBoxLayout(converter_group)
        
        # Input section
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Convert:"))
        self.convert_value_input = QDoubleSpinBox()
        self.convert_value_input.setRange(0.001, 1000000)
        self.convert_value_input.setValue(100.0)
        self.convert_value_input.setDecimals(6)
        input_layout.addWidget(self.convert_value_input)
        
        self.convert_from_unit = QComboBox()
        self.convert_from_unit.addItems(["nM", "µM", "pM", "mM", "M", "ng/mL", "µg/mL", "mg/mL"])
        input_layout.addWidget(self.convert_from_unit)
        
        input_layout.addWidget(QLabel("to"))
        
        self.convert_to_unit = QComboBox()
        self.convert_to_unit.addItems(["nM", "µM", "pM", "mM", "M", "ng/mL", "µg/mL", "mg/mL"])
        self.convert_to_unit.setCurrentText("µg/mL")
        input_layout.addWidget(self.convert_to_unit)
        
        convert_btn = QPushButton("Convert")
        convert_btn.clicked.connect(self._convert_concentration)
        input_layout.addWidget(convert_btn)
        
        input_layout.addStretch()
        converter_layout.addLayout(input_layout)
        
        # MW input for mass/molar conversions
        mw_layout = QHBoxLayout()
        mw_layout.addWidget(QLabel("Molecular Weight (for mass ↔ molar):"))
        self.converter_mw_input = QDoubleSpinBox()
        self.converter_mw_input.setRange(100, 1000000)
        self.converter_mw_input.setValue(150000)
        self.converter_mw_input.setSuffix(" Da")
        self.converter_mw_input.setToolTip("Use analyte MW from Protein Setup tab")
        mw_layout.addWidget(self.converter_mw_input)
        
        use_analyte_btn = QPushButton("Use Analyte MW")
        use_analyte_btn.clicked.connect(self._use_analyte_mw_converter)
        mw_layout.addWidget(use_analyte_btn)
        
        mw_layout.addStretch()
        converter_layout.addLayout(mw_layout)
        
        # Result display
        self.converter_result_label = QLabel("")
        self.converter_result_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #007AFF; padding: 20px;"
        )
        self.converter_result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        converter_layout.addWidget(self.converter_result_label)
        
        layout.addWidget(converter_group)
        
        # Quick conversions table
        quick_group = QGroupBox("Quick Reference: Common Protein Concentrations")
        quick_layout = QVBoxLayout(quick_group)
        
        self.quick_conversion_table = QTableWidget()
        self.quick_conversion_table.setColumnCount(3)
        self.quick_conversion_table.setHorizontalHeaderLabels(["nM", "µM", "µg/mL (150 kDa)"])
        self.quick_conversion_table.setRowCount(8)
        
        # Populate with common values
        common_nm = [1, 10, 50, 100, 500, 1000, 5000, 10000]
        for i, nm in enumerate(common_nm):
            # nM
            self.quick_conversion_table.setItem(i, 0, QTableWidgetItem(f"{nm}"))
            # µM
            um = nm / 1000
            self.quick_conversion_table.setItem(i, 1, QTableWidgetItem(f"{um:.3f}"))
            # µg/mL (assuming 150 kDa)
            ug_ml = (nm * 1e-9) * 150000  # M to g/L = µg/mL
            self.quick_conversion_table.setItem(i, 2, QTableWidgetItem(f"{ug_ml:.3f}"))
        
        quick_layout.addWidget(self.quick_conversion_table)
        layout.addWidget(quick_group)
        
        # Conversion formulas
        formula_group = QGroupBox("Conversion Formulas")
        formula_layout = QVBoxLayout(formula_group)
        
        formulas = QTextEdit()
        formulas.setReadOnly(True)
        formulas.setMaximumHeight(150)
        formulas.setStyleSheet("background: #F5F5F7; font-family: 'Consolas', monospace;")
        formulas.setText(
            "Mass → Molar Conversion:\n"
            "  Concentration (M) = Concentration (g/L) / MW (Da)\n"
            "  Example: 15 µg/mL ÷ 150,000 Da = 100 nM\n\n"
            "Molar → Mass Conversion:\n"
            "  Concentration (g/L) = Concentration (M) × MW (Da)\n"
            "  Example: 100 nM × 150,000 Da = 15 µg/mL\n\n"
            "Where:\n"
            "  1 µg/mL = 1 g/L\n"
            "  1 nM = 1 × 10⁻⁹ M"
        )
        formula_layout.addWidget(formulas)
        
        layout.addWidget(formula_group)
        
        layout.addStretch()
        
        return widget
    
    def _use_analyte_mw_converter(self):
        """Copy analyte MW to converter."""
        mw_da = self.analyte_mw_input.value() * 1000  # kDa to Da
        self.converter_mw_input.setValue(mw_da)
    
    def _convert_concentration(self):
        """Perform concentration conversion."""
        value = self.convert_value_input.value()
        from_unit = self.convert_from_unit.currentText()
        to_unit = self.convert_to_unit.currentText()
        mw_da = self.converter_mw_input.value()
        
        try:
            result = self.protein_util.convert_concentration(value, from_unit, to_unit, mw_da)
            
            if result is not None:
                self.converter_result_label.setText(
                    f"✓  {value:.6g} {from_unit}  =  {result:.6g} {to_unit}"
                )
            else:
                self.converter_result_label.setText("❌ Conversion failed")
        except Exception as e:
            self.converter_result_label.setText(f"❌ Error: {str(e)}")
    
    # ========================================================================
    # File Operations
    # ========================================================================
    
    def _new_experiment(self):
        """Start a new experiment."""
        reply = QMessageBox.question(
            self, "New Experiment",
            "Start a new experiment? Unsaved changes will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._clear_all_fields()
            self.current_experiment_file = None
            self.setWindowTitle("SPR Experiment Planner - AffiLabs.core [New Experiment]")
    
    def _clear_all_fields(self):
        """Clear all input fields."""
        # Ligand
        self.ligand_uniprot_input.clear()
        self.ligand_name_input.clear()
        self.ligand_mw_input.setValue(150.0)
        self.ligand_info_label.setText("No ligand loaded")
        self.ligand_data = None
        
        # Analyte
        self.analyte_uniprot_input.clear()
        self.analyte_name_input.clear()
        self.analyte_mw_input.setValue(50.0)
        self.analyte_info_label.setText("No analyte loaded")
        self.analyte_data = None
        
        # Parameters
        self.stoichiometry_input.setValue(1)
        self.kd_value_input.setValue(10.0)
        self.kd_unit_combo.setCurrentText("nM")
        
        # Clear results
        self.required_immob_label.clear()
        self.theoretical_rmax_label.clear()
        self.immob_recommendations.clear()
        self.concentration_table.setRowCount(0)
        self.validation_results.clear()
    
    def _open_experiment(self):
        """Open saved experiment."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Experiment",
            str(self.experiments_dir),
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            self._load_experiment(Path(file_path))
    
    def _load_experiment(self, file_path: Path):
        """Load experiment from file."""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Load ligand
            if 'ligand' in data:
                lig = data['ligand']
                self.ligand_name_input.setText(lig.get('name', ''))
                self.ligand_mw_input.setValue(lig.get('mw_kda', 150.0))
                if 'uniprot_id' in lig:
                    self.ligand_uniprot_input.setText(lig['uniprot_id'])
            
            # Load analyte
            if 'analyte' in data:
                ana = data['analyte']
                self.analyte_name_input.setText(ana.get('name', ''))
                self.analyte_mw_input.setValue(ana.get('mw_kda', 50.0))
                if 'uniprot_id' in ana:
                    self.analyte_uniprot_input.setText(ana['uniprot_id'])
            
            # Load parameters
            if 'parameters' in data:
                params = data['parameters']
                self.stoichiometry_input.setValue(params.get('stoichiometry', 1))
                self.kd_value_input.setValue(params.get('kd_value', 10.0))
                self.kd_unit_combo.setCurrentText(params.get('kd_unit', 'nM'))
                self.immob_level_input.setValue(params.get('immob_level', 1000.0))
                self.target_rmax_input.setValue(params.get('target_rmax', 500.0))
            
            self.current_experiment_file = file_path
            self.setWindowTitle(f"SPR Experiment Planner - {file_path.name}")
            
            QMessageBox.information(self, "Success", f"Loaded experiment from:\n{file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load experiment:\n{str(e)}")
    
    def _save_experiment(self):
        """Save current experiment."""
        if self.current_experiment_file:
            self._save_experiment_to_file(self.current_experiment_file)
        else:
            self._save_experiment_as()
    
    def _save_experiment_as(self):
        """Save experiment with new filename."""
        default_name = f"experiment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Experiment As",
            str(self.experiments_dir / default_name),
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            self._save_experiment_to_file(Path(file_path))
    
    def _save_experiment_to_file(self, file_path: Path):
        """Save experiment data to file."""
        try:
            data = {
                'version': '1.0',
                'created': datetime.now().isoformat(),
                'ligand': {
                    'name': self.ligand_name_input.text(),
                    'mw_kda': self.ligand_mw_input.value(),
                    'uniprot_id': self.ligand_uniprot_input.text() or None
                },
                'analyte': {
                    'name': self.analyte_name_input.text(),
                    'mw_kda': self.analyte_mw_input.value(),
                    'uniprot_id': self.analyte_uniprot_input.text() or None
                },
                'parameters': {
                    'stoichiometry': self.stoichiometry_input.value(),
                    'kd_value': self.kd_value_input.value(),
                    'kd_unit': self.kd_unit_combo.currentText(),
                    'immob_level': self.immob_level_input.value(),
                    'target_rmax': self.target_rmax_input.value(),
                    'num_concentrations': self.num_concentrations_input.value()
                }
            }
            
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.current_experiment_file = file_path
            self.setWindowTitle(f"SPR Experiment Planner - {file_path.name}")
            
            QMessageBox.information(self, "Success", f"Saved experiment to:\n{file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save experiment:\n{str(e)}")
    
    def _export_report(self):
        """Export experiment plan as text report."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Report",
            str(self.experiments_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"),
            "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    f.write("="*80 + "\n")
                    f.write("SPR EXPERIMENT PLAN\n")
                    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("="*80 + "\n\n")
                    
                    # Proteins
                    f.write("PROTEINS\n")
                    f.write("-"*80 + "\n")
                    f.write(f"Ligand (Immobilized):\n")
                    f.write(f"  Name: {self.ligand_name_input.text()}\n")
                    f.write(f"  MW: {self.ligand_mw_input.value()} kDa\n")
                    if self.ligand_uniprot_input.text():
                        f.write(f"  UniProt: {self.ligand_uniprot_input.text()}\n")
                    
                    f.write(f"\nAnalyte (Flowing):\n")
                    f.write(f"  Name: {self.analyte_name_input.text()}\n")
                    f.write(f"  MW: {self.analyte_mw_input.value()} kDa\n")
                    if self.analyte_uniprot_input.text():
                        f.write(f"  UniProt: {self.analyte_uniprot_input.text()}\n")
                    f.write("\n")
                    
                    # Parameters
                    f.write("PARAMETERS\n")
                    f.write("-"*80 + "\n")
                    f.write(f"Stoichiometry: {self.stoichiometry_input.value()}:1\n")
                    f.write(f"Estimated KD: {self.kd_value_input.value()} {self.kd_unit_combo.currentText()}\n")
                    f.write(f"Target Immobilization: {self.immob_level_input.value()} RU\n")
                    f.write("\n")
                    
                    # Concentration table
                    if self.concentration_table.rowCount() > 0:
                        f.write("CONCENTRATION SERIES\n")
                        f.write("-"*80 + "\n")
                        for row in range(self.concentration_table.rowCount()):
                            conc_nm = self.concentration_table.item(row, 0).text() if self.concentration_table.item(row, 0) else ""
                            conc_ug = self.concentration_table.item(row, 1).text() if self.concentration_table.item(row, 1) else ""
                            resp = self.concentration_table.item(row, 3).text() if self.concentration_table.item(row, 3) else ""
                            f.write(f"  {conc_nm:>10} nM  =  {conc_ug:>10} µg/mL  →  {resp:>8} RU\n")
                        f.write("\n")
                    
                    f.write("="*80 + "\n")
                
                QMessageBox.information(self, "Success", f"Report exported to:\n{file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export report:\n{str(e)}")
    
    # ========================================================================
    # Custom Protein Management
    # ========================================================================
    
    def _load_custom_proteins(self) -> Dict:
        """Load custom protein library."""
        if self.custom_proteins_file.exists():
            try:
                with open(self.custom_proteins_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_custom_proteins(self):
        """Save custom protein library."""
        self.custom_proteins_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.custom_proteins_file, 'w') as f:
            json.dump(self.custom_proteins, f, indent=2)
    
    def _add_custom_protein(self):
        """Add custom protein to library."""
        from PySide6.QtWidgets import QFormLayout
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Custom Protein")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        
        name_input = QLineEdit()
        name_input.setPlaceholderText("e.g., My Custom Antibody")
        form.addRow("Protein Name:", name_input)
        
        mw_input = QDoubleSpinBox()
        mw_input.setRange(1, 10000)
        mw_input.setValue(150.0)
        mw_input.setSuffix(" kDa")
        form.addRow("Molecular Weight:", mw_input)
        
        notes_input = QTextEdit()
        notes_input.setPlaceholderText("Optional notes...")
        notes_input.setMaximumHeight(100)
        form.addRow("Notes:", notes_input)
        
        layout.addLayout(form)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = name_input.text().strip()
            if name:
                protein_id = name.lower().replace(' ', '_')
                self.custom_proteins[protein_id] = {
                    'name': name,
                    'mw_kda': mw_input.value(),
                    'notes': notes_input.toPlainText(),
                    'created': datetime.now().isoformat()
                }
                self._save_custom_proteins()
                QMessageBox.information(self, "Success", f"Added '{name}' to custom proteins")
    
    def _view_custom_proteins(self):
        """View and manage custom proteins."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Custom Protein Library")
        dialog.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        proteins_list = QListWidget()
        for protein_id, data in self.custom_proteins.items():
            item = QListWidgetItem(f"{data['name']} ({data['mw_kda']} kDa)")
            item.setData(Qt.ItemDataRole.UserRole, protein_id)
            proteins_list.addItem(item)
        
        layout.addWidget(proteins_list)
        
        button_layout = QHBoxLayout()
        
        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(lambda: self._delete_custom_protein(proteins_list, dialog))
        button_layout.addWidget(delete_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        dialog.exec()
    
    def _delete_custom_protein(self, list_widget: QListWidget, dialog: QDialog):
        """Delete selected custom protein."""
        current_item = list_widget.currentItem()
        if current_item:
            protein_id = current_item.data(Qt.ItemDataRole.UserRole)
            protein_name = self.custom_proteins[protein_id]['name']
            
            reply = QMessageBox.question(
                dialog, "Confirm Delete",
                f"Delete '{protein_name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                del self.custom_proteins[protein_id]
                self._save_custom_proteins()
                list_widget.takeItem(list_widget.row(current_item))
                QMessageBox.information(dialog, "Deleted", f"Removed '{protein_name}'")
    
    def _load_custom_protein(self, protein_type: str):
        """Load custom protein into form."""
        if not self.custom_proteins:
            QMessageBox.information(self, "No Custom Proteins", 
                                   "No custom proteins saved. Add one from Proteins menu.")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Select {protein_type.title()}")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(dialog)
        
        proteins_list = QListWidget()
        for protein_id, data in self.custom_proteins.items():
            item = QListWidgetItem(f"{data['name']} ({data['mw_kda']} kDa)")
            item.setData(Qt.ItemDataRole.UserRole, protein_id)
            proteins_list.addItem(item)
        
        proteins_list.itemDoubleClicked.connect(dialog.accept)
        layout.addWidget(proteins_list)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            current_item = proteins_list.currentItem()
            if current_item:
                protein_id = current_item.data(Qt.ItemDataRole.UserRole)
                data = self.custom_proteins[protein_id]
                
                if protein_type == 'ligand':
                    self.ligand_name_input.setText(data['name'])
                    self.ligand_mw_input.setValue(data['mw_kda'])
                    self.ligand_info_label.setText(f"✓ Custom: {data['name']}\n  {data['mw_kda']} kDa")
                else:
                    self.analyte_name_input.setText(data['name'])
                    self.analyte_mw_input.setValue(data['mw_kda'])
                    self.analyte_info_label.setText(f"✓ Custom: {data['name']}\n  {data['mw_kda']} kDa")
    
    def _import_protein_library(self):
        """Import protein library from JSON."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Protein Library", "", "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    imported = json.load(f)
                
                # Merge with existing
                count = 0
                for protein_id, data in imported.items():
                    if protein_id not in self.custom_proteins:
                        self.custom_proteins[protein_id] = data
                        count += 1
                
                self._save_custom_proteins()
                QMessageBox.information(self, "Success", f"Imported {count} new proteins")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import:\n{str(e)}")
    
    def _export_protein_library(self):
        """Export protein library to JSON."""
        if not self.custom_proteins:
            QMessageBox.information(self, "No Proteins", "No custom proteins to export")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Protein Library",
            f"protein_library_{datetime.now().strftime('%Y%m%d')}.json",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    json.dump(self.custom_proteins, f, indent=2)
                
                QMessageBox.information(self, "Success", f"Exported to:\n{file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export:\n{str(e)}")
    
    def _get_stylesheet(self) -> str:
        """Return application stylesheet."""
        return """
        QMainWindow {
            background: #FFFFFF;
        }
        QGroupBox {
            font-weight: bold;
            border: 2px solid #D1D1D6;
            border-radius: 6px;
            margin-top: 12px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 10px;
            padding: 0 5px;
            color: #1D1D1F;
        }
        QPushButton {
            background: #007AFF;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: bold;
        }
        QPushButton:hover {
            background: #0051D5;
        }
        QPushButton:pressed {
            background: #004DB8;
        }
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            border: 1px solid #D1D1D6;
            border-radius: 4px;
            padding: 6px;
            background: white;
        }
        QTableWidget {
            border: 1px solid #D1D1D6;
            gridline-color: #E5E5EA;
        }
        QHeaderView::section {
            background: #F5F5F7;
            padding: 6px;
            border: none;
            border-right: 1px solid #D1D1D6;
            border-bottom: 1px solid #D1D1D6;
            font-weight: bold;
        }
        QTabWidget::pane {
            border: 1px solid #D1D1D6;
            border-radius: 4px;
        }
        QTabBar::tab {
            background: #F5F5F7;
            border: 1px solid #D1D1D6;
            padding: 8px 20px;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background: white;
            border-bottom-color: white;
        }
        """


def main():
    """Run the SPR Experiment Planner."""
    app = QApplication(sys.argv)
    
    # Set application metadata
    app.setApplicationName("SPR Experiment Planner")
    app.setOrganizationName("AffiLabs")
    
    # Create and show main window
    window = ExperimentPlannerUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
