"""SPR Experiment Planner - AffiLabs Design System
Modern single-page layout with collapsible sections
Matches AffiLabs.core UI styling and design patterns
"""

import sys
import json
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QThread, Slot
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QGroupBox, QComboBox, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog, QDialogButtonBox,
    QTextEdit, QListWidget, QListWidgetItem, QMessageBox, QFileDialog, QSplitter, QFrame,
    QSpinBox, QDoubleSpinBox
)
from PySide6.QtGui import QFont, QColor, QAction

try:
    from protein_utils import ProteinUtility
except ImportError as e:
    print(f"Warning: Could not import protein_utils: {e}")
    print("UniProt features will be disabled.")
    ProteinUtility = None


# ============================================================================
# DESIGN TOKENS - AffiLabs Design System
# ============================================================================

class Colors:
    """AffiLabs color palette - grayscale theme"""
    GRAY_900 = "#1D1D1F"
    GRAY_700 = "#3A3A3C"
    GRAY_600 = "#48484A"
    GRAY_500 = "#86868B"
    GRAY_300 = "rgba(0, 0, 0, 0.1)"
    GRAY_100 = "rgba(0, 0, 0, 0.06)"
    GRAY_50 = "#F5F5F7"
    
    SURFACE = "#FFFFFF"
    BACKGROUND = "#F8F9FA"
    
    SUCCESS = "#34C759"
    SUCCESS_HOVER = "#2FB350"
    ERROR = "#FF3B30"
    ERROR_HOVER = "#E6342A"
    WARNING = "#FFCC00"
    WARNING_HOVER = "#E6B800"
    
    OUTLINE = "rgba(0, 0, 0, 0.1)"


class Spacing:
    """8px base unit spacing system"""
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 20
    XXL = 24


class Radius:
    """Border radius values"""
    SM = 4
    MD = 8
    LG = 12


class Typography:
    """Font system"""
    FAMILY = "-apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif"
    SIZE_BODY_SMALL = 8
    SIZE_BODY = 9
    SIZE_SUBTITLE = 10
    SIZE_TITLE = 11
    SIZE_HEADLINE = 13


# ============================================================================
# STYLESHEET GENERATORS
# ============================================================================

def get_button_style(variant: str = "standard") -> str:
    """Generate button stylesheet matching AffiLabs design"""
    variants = {
        "standard": {
            "bg": "rgba(0, 0, 0, 0.06)",
            "hover": "rgba(0, 0, 0, 0.1)",
            "text": Colors.GRAY_900,
        },
        "primary": {
            "bg": Colors.GRAY_900,
            "hover": Colors.GRAY_700,
            "text": "white",
        },
        "success": {
            "bg": Colors.SUCCESS,
            "hover": Colors.SUCCESS_HOVER,
            "text": "white",
        },
        "error": {
            "bg": Colors.ERROR,
            "hover": Colors.ERROR_HOVER,
            "text": "white",
        },
    }
    
    style = variants.get(variant, variants["standard"])
    
    return f"""
    QPushButton {{
        background: {style['bg']};
        border: none;
        border-radius: 4px;
        color: {style['text']};
        padding: 4px 12px;
        font-family: {Typography.FAMILY};
        font-size: 11px;
        font-weight: normal;
        min-height: 20px;
    }}
    QPushButton:hover {{
        background: {style['hover']};
    }}
    QPushButton:disabled {{
        background: rgba(0, 0, 0, 0.03);
        color: {Colors.GRAY_500};
        opacity: 0.5;
    }}
    """


def get_groupbox_style() -> str:
    """Generate QGroupBox stylesheet matching AffiLabs design"""
    return f"""
    QGroupBox {{
        background-color: {Colors.SURFACE};
        border: 1px solid {Colors.OUTLINE};
        border-radius: 4px;
        padding: 12px;
        margin-top: 18px;
        font-family: {Typography.FAMILY};
        font-size: 13px;
        font-weight: 600;
        color: {Colors.GRAY_900};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 8px;
        padding: 0 6px;
        background-color: {Colors.SURFACE};
    }}
    """


def get_input_style() -> str:
    """Generate input field stylesheet"""
    return f"""
    QLineEdit, QSpinBox, QDoubleSpinBox {{
        background-color: {Colors.SURFACE};
        border: 1px solid {Colors.OUTLINE};
        border-radius: 4px;
        padding: 4px 8px;
        font-family: {Typography.FAMILY};
        font-size: 9pt;
        color: {Colors.GRAY_900};
        min-height: 18px;
    }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
        border: 1px solid {Colors.GRAY_900};
    }}
    QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
        background-color: {Colors.GRAY_50};
        color: {Colors.GRAY_500};
    }}
    """


def get_combobox_style() -> str:
    """Generate combobox stylesheet"""
    return f"""
    QComboBox {{
        background-color: {Colors.SURFACE};
        border: 1px solid {Colors.OUTLINE};
        border-radius: 4px;
        padding: 4px 8px;
        font-family: {Typography.FAMILY};
        font-size: 9pt;
        color: {Colors.GRAY_900};
        min-height: 18px;
    }}
    QComboBox:focus {{
        border: 1px solid {Colors.GRAY_900};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {Colors.GRAY_900};
        margin-right: 8px;
    }}
    """


def get_label_style(bold: bool = False, size: int = 9) -> str:
    """Generate label stylesheet"""
    weight = "600" if bold else "400"
    return f"""
    QLabel {{
        font-family: {Typography.FAMILY};
        font-size: {size}pt;
        font-weight: {weight};
        color: {Colors.GRAY_900};
    }}
    """


# ============================================================================
# WORKER THREADS
# ============================================================================

class UniProtLookupThread(QThread):
    """Background thread for UniProt data fetching"""
    finished = Signal(dict)
    error = Signal(str)
    
    def __init__(self, uniprot_id: str):
        super().__init__()
        self.uniprot_id = uniprot_id
        self.protein_util = ProteinUtility() if ProteinUtility else None
    
    def run(self):
        if not self.protein_util:
            self.error.emit("ProteinUtility not available")
            return
        
        try:
            data = self.protein_util.fetch_uniprot_data(self.uniprot_id)
            if data:
                self.finished.emit(data)
            else:
                self.error.emit(f"No data found for {self.uniprot_id}")
        except Exception as e:
            self.error.emit(str(e))


class UniProtSearchThread(QThread):
    """Background thread for UniProt search"""
    finished = Signal(list)
    error = Signal(str)
    
    def __init__(self, query: str, organism: str = ""):
        super().__init__()
        self.query = query
        self.organism = organism
        self.protein_util = ProteinUtility() if ProteinUtility else None
    
    def run(self):
        if not self.protein_util:
            self.error.emit("ProteinUtility not available")
            return
        
        try:
            results = self.protein_util.search_uniprot_by_name(
                self.query, 
                organism=self.organism, 
                limit=10
            )
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


# ============================================================================
# PROTEIN SEARCH DIALOG
# ============================================================================

class ProteinSearchDialog(QDialog):
    """Dialog for searching proteins in UniProt database"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_protein = None
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("Search UniProt Database")
        self.setMinimumSize(700, 500)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(Spacing.MD)
        
        # Search inputs
        search_group = QGroupBox("Search Parameters")
        search_group.setStyleSheet(get_groupbox_style())
        search_layout = QVBoxLayout()
        
        # Protein name
        name_layout = QHBoxLayout()
        name_label = QLabel("Protein Name:")
        name_label.setMinimumWidth(100)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., TNF-alpha, IgG, Insulin")
        self.name_input.setStyleSheet(get_input_style())
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_input)
        search_layout.addLayout(name_layout)
        
        # Organism
        org_layout = QHBoxLayout()
        org_label = QLabel("Organism:")
        org_label.setMinimumWidth(100)
        self.organism_input = QLineEdit()
        self.organism_input.setPlaceholderText("e.g., Human, Mouse (optional)")
        self.organism_input.setStyleSheet(get_input_style())
        org_layout.addWidget(org_label)
        org_layout.addWidget(self.organism_input)
        search_layout.addLayout(org_layout)
        
        # Search button
        self.search_btn = QPushButton("Search")
        self.search_btn.setStyleSheet(get_button_style("primary"))
        self.search_btn.clicked.connect(self._perform_search)
        search_layout.addWidget(self.search_btn)
        
        search_group.setLayout(search_layout)
        layout.addWidget(search_group)
        
        # Results list
        results_label = QLabel("Search Results:")
        results_label.setStyleSheet(get_label_style(bold=True))
        layout.addWidget(results_label)
        
        self.results_list = QListWidget()
        self.results_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.OUTLINE};
                border-radius: {Radius.SM}px;
                font-family: {Typography.FAMILY};
                font-size: {Typography.SIZE_BODY}pt;
                padding: {Spacing.XS}px;
            }}
            QListWidget::item {{
                padding: {Spacing.SM}px;
                border-bottom: 1px solid {Colors.OUTLINE};
            }}
            QListWidget::item:selected {{
                background-color: {Colors.GRAY_100};
                color: {Colors.GRAY_900};
            }}
        """)
        self.results_list.itemDoubleClicked.connect(self._select_protein)
        layout.addWidget(self.results_list)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(get_label_style())
        layout.addWidget(self.status_label)
        
        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self._select_protein)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _perform_search(self):
        query = self.name_input.text().strip()
        organism = self.organism_input.text().strip()
        
        if not query:
            self.status_label.setText("❌ Please enter a protein name")
            return
        
        self.status_label.setText("🔍 Searching UniProt...")
        self.results_list.clear()
        self.search_btn.setEnabled(False)
        
        self.search_thread = UniProtSearchThread(query, organism)
        self.search_thread.finished.connect(self._display_results)
        self.search_thread.error.connect(self._handle_error)
        self.search_thread.start()
    
    @Slot(list)
    def _display_results(self, results):
        self.search_btn.setEnabled(True)
        
        if not results:
            self.status_label.setText("❌ No results found")
            return
        
        self.status_label.setText(f"✓ Found {len(results)} results")
        
        for protein in results:
            name = protein.get('name', 'Unknown')
            uniprot_id = protein.get('uniprot_id', '')
            organism = protein.get('organism', '')
            mw_kda = protein.get('mw_kda', 0)
            
            item_text = f"{name} ({uniprot_id}) - {organism} - {mw_kda:.2f} kDa"
            self.results_list.addItem(item_text)
        
        # Store full data
        self.results_data = results
    
    @Slot(str)
    def _handle_error(self, error_msg):
        self.search_btn.setEnabled(True)
        self.status_label.setText(f"❌ Error: {error_msg}")
    
    def _select_protein(self):
        current_item = self.results_list.currentItem()
        if current_item:
            idx = self.results_list.row(current_item)
            self.selected_protein = self.results_data[idx]
            self.accept()


# ============================================================================
# MAIN PLANNER UI
# ============================================================================

class SPRExperimentPlanner(QMainWindow):
    """Main SPR Experiment Planner Window"""
    
    def __init__(self):
        super().__init__()
        self.protein_util = ProteinUtility() if ProteinUtility else None
        self.custom_proteins_file = Path.home() / '.spr_planner' / 'custom_proteins.json'
        self.experiments_dir = Path.home() / '.spr_planner' / 'experiments'
        self.current_experiment_file: Optional[Path] = None
        self.custom_proteins = self._load_custom_proteins()
        
        self.init_ui()
        self.setWindowTitle("SPR Experiment Planner - AffiLabs")
        self.resize(1200, 900)
    
    def init_ui(self):
        """Initialize the user interface"""
        # Create menu bar
        self._create_menu_bar()
        
        # Central widget with scroll area
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)
        main_layout.setSpacing(Spacing.MD)
        
        # Title
        title = QLabel("SPR Experiment Planner")
        title.setStyleSheet(f"""
            QLabel {{
                font-family: {Typography.FAMILY};
                font-size: 15px;
                font-weight: 600;
                color: {Colors.GRAY_900};
                padding: 8px 0;
            }}
        """)
        main_layout.addWidget(title)
        
        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ background-color: {Colors.BACKGROUND}; border: none; }}")
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(8)
        scroll_layout.setContentsMargins(0, 0, 8, 0)
        
        # Add all sections with better layout
        
        # Top section: Search on left, Summary table on right
        top_section = QHBoxLayout()
        top_section.setSpacing(12)
        top_section.addWidget(self._create_protein_section(), 1)
        top_section.addWidget(self._create_summary_table(), 1)
        scroll_layout.addLayout(top_section)
        
        # Parameters section
        scroll_layout.addWidget(self._create_experiment_parameters())
        
        # Concentration series and validation side by side
        conc_val_layout = QHBoxLayout()
        conc_val_layout.setSpacing(Spacing.MD)
        conc_val_layout.addWidget(self._create_concentration_series(), 2)
        conc_val_layout.addWidget(self._create_validation_section(), 1)
        conc_val_widget = QWidget()
        conc_val_widget.setLayout(conc_val_layout)
        scroll_layout.addWidget(conc_val_widget)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)
        
        # Apply background color
        self.setStyleSheet(f"QMainWindow {{ background-color: {Colors.BACKGROUND}; }}")
    
    def _create_menu_bar(self):
        """Create menu bar with file operations"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        new_action = QAction("New Experiment", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._new_experiment)
        file_menu.addAction(new_action)
        
        open_action = QAction("Open Experiment", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._load_experiment)
        file_menu.addAction(open_action)
        
        save_action = QAction("Save Experiment", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_experiment)
        file_menu.addAction(save_action)
        
        save_as_action = QAction("Save As...", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(lambda: self._save_experiment(save_as=True))
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        export_action = QAction("Export Report", self)
        export_action.triggered.connect(self._export_report)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        quit_action = QAction("Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)
        
        # Proteins menu
        proteins_menu = menubar.addMenu("Proteins")
        
        add_custom_action = QAction("Add Custom Protein", self)
        add_custom_action.triggered.connect(self._add_custom_protein)
        proteins_menu.addAction(add_custom_action)
        
        view_custom_action = QAction("View Custom Proteins", self)
        view_custom_action.triggered.connect(self._view_custom_proteins)
        proteins_menu.addAction(view_custom_action)
        
        proteins_menu.addSeparator()
        
        import_lib_action = QAction("Import Protein Library", self)
        import_lib_action.triggered.connect(self._import_protein_library)
        proteins_menu.addAction(import_lib_action)
        
        export_lib_action = QAction("Export Protein Library", self)
        export_lib_action.triggered.connect(self._export_protein_library)
        proteins_menu.addAction(export_lib_action)
    
    def _create_protein_section(self) -> QGroupBox:
        """Create protein search section"""
        group = QGroupBox("Protein Search")
        group.setStyleSheet(get_groupbox_style())
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        # Source label
        source_label = QLabel("Source: UniProt")
        source_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.GRAY_600};
                font-size: 8pt;
                font-style: italic;
            }}
        """)
        layout.addWidget(source_label)
        
        # Search by ID
        id_layout = QHBoxLayout()
        id_layout.setSpacing(8)
        
        id_label = QLabel("ID:")
        id_label.setMinimumWidth(60)
        id_label.setStyleSheet(get_label_style())
        
        self.protein_uniprot_input = QLineEdit()
        self.protein_uniprot_input.setPlaceholderText("e.g., P01375")
        self.protein_uniprot_input.setStyleSheet(get_input_style())
        
        self.protein_lookup_btn = QPushButton("Lookup")
        self.protein_lookup_btn.setStyleSheet(get_button_style("primary"))
        self.protein_lookup_btn.clicked.connect(self._lookup_protein_with_role)
        
        id_layout.addWidget(id_label)
        id_layout.addWidget(self.protein_uniprot_input, 1)
        id_layout.addWidget(self.protein_lookup_btn)
        
        layout.addLayout(id_layout)
        
        # Search by name
        name_layout = QHBoxLayout()
        name_layout.setSpacing(8)
        
        name_label = QLabel("Name:")
        name_label.setMinimumWidth(60)
        name_label.setStyleSheet(get_label_style())
        
        self.protein_name_input = QLineEdit()
        self.protein_name_input.setPlaceholderText("e.g., insulin, TNF")
        self.protein_name_input.setStyleSheet(get_input_style())
        
        self.organism_combo = QComboBox()
        self.organism_combo.addItems(["Human", "Mouse", "Rat", "Any"])
        self.organism_combo.setStyleSheet(get_combobox_style())
        self.organism_combo.setMaximumWidth(100)
        
        self.protein_search_btn = QPushButton("Search")
        self.protein_search_btn.setStyleSheet(get_button_style("standard"))
        self.protein_search_btn.clicked.connect(self._search_protein_inline)
        
        self.load_custom_btn = QPushButton("Load Custom")
        self.load_custom_btn.setStyleSheet(get_button_style("standard"))
        self.load_custom_btn.clicked.connect(self._show_custom_proteins)
        
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.protein_name_input, 1)
        name_layout.addWidget(self.organism_combo)
        name_layout.addWidget(self.protein_search_btn)
        name_layout.addWidget(self.load_custom_btn)
        
        layout.addLayout(name_layout)
        
        # Search results list
        self.search_results_list = QListWidget()
        self.search_results_list.setMaximumHeight(100)
        self.search_results_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.OUTLINE};
                border-radius: 4px;
                font-size: 8pt;
                padding: 2px;
                color: {Colors.GRAY_900};
            }}
            QListWidget::item {{
                padding: 4px;
                border-radius: 2px;
                color: {Colors.GRAY_900};
            }}
            QListWidget::item:hover {{
                background-color: {Colors.GRAY_100};
                color: {Colors.GRAY_900};
            }}
            QListWidget::item:selected {{
                background-color: {Colors.GRAY_300};
                color: {Colors.GRAY_900};
            }}
        """)
        self.search_results_list.itemClicked.connect(self._select_search_result)
        self.search_results_list.hide()
        layout.addWidget(self.search_results_list)
        
        # Tags section - clickable to assign
        tags_label = QLabel("Assign protein to:")
        tags_label.setStyleSheet(f"color: {Colors.GRAY_600}; font-size: 8pt;")
        layout.addWidget(tags_label)
        
        tags_layout = QHBoxLayout()
        tags_layout.setSpacing(6)
        
        # Ligand tag button
        self.ligand_tag_btn = QPushButton("Ligand")
        self.ligand_tag_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.GRAY_100};
                border: 1px solid {Colors.OUTLINE};
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 8pt;
                color: {Colors.GRAY_700};
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Colors.GRAY_300};
                border-color: {Colors.GRAY_500};
            }}
            QPushButton:pressed {{
                background-color: {Colors.GRAY_500};
                color: {Colors.SURFACE};
            }}
        """)
        self.ligand_tag_btn.clicked.connect(lambda: self._assign_protein_to_role("Ligand"))
        
        # Target tag button
        self.target_tag_btn = QPushButton("Target")
        self.target_tag_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.GRAY_100};
                border: 1px solid {Colors.OUTLINE};
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 8pt;
                color: {Colors.GRAY_700};
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Colors.GRAY_300};
                border-color: {Colors.GRAY_500};
            }}
            QPushButton:pressed {{
                background-color: {Colors.GRAY_500};
                color: {Colors.SURFACE};
            }}
        """)
        self.target_tag_btn.clicked.connect(lambda: self._assign_protein_to_role("Target"))
        
        tags_layout.addWidget(self.ligand_tag_btn)
        tags_layout.addWidget(self.target_tag_btn)
        tags_layout.addStretch()
        
        layout.addLayout(tags_layout)
        
        # Current selection display
        self.current_protein_label = QLabel("No protein selected")
        self.current_protein_label.setStyleSheet(f"color: {Colors.GRAY_900}; font-size: 8pt; font-style: italic;")
        layout.addWidget(self.current_protein_label)
        
        # Store current protein data
        self.current_protein_data = None
        
        # Store MW values (hidden)
        self.ligand_mw_input = QDoubleSpinBox()
        self.ligand_mw_input.setValue(150.0)
        self.ligand_mw_input.valueChanged.connect(self._update_summary_table)
        
        self.target_mw_input = QDoubleSpinBox()
        self.target_mw_input.setValue(50.0)
        self.target_mw_input.valueChanged.connect(self._update_summary_table)
        
        group.setLayout(layout)
        return group
    
    def _lookup_protein_with_role(self):
        """Lookup protein and ask for role assignment"""
        uniprot_id = self.protein_uniprot_input.text().strip()
        if not uniprot_id:
            QMessageBox.warning(self, "Missing ID", "Please enter a UniProt ID")
            return
        
        self.protein_lookup_btn.setEnabled(False)
        self.protein_lookup_btn.setText("Looking up...")
        
        self.lookup_thread = UniProtLookupThread(uniprot_id)
        self.lookup_thread.finished.connect(self._assign_role_after_lookup)
        self.lookup_thread.error.connect(self._handle_lookup_error)
        self.lookup_thread.start()
    
    @Slot(dict)
    def _assign_role_after_lookup(self, data: dict):
        """Ask user to assign role after successful lookup"""
        self.protein_lookup_btn.setEnabled(True)
        self.protein_lookup_btn.setText("Lookup")
        
        # Ask user for role
        dialog = QDialog(self)
        dialog.setWindowTitle("Assign Protein Role")
        dialog.setMinimumWidth(300)
        
        layout = QVBoxLayout(dialog)
        
        info_label = QLabel(f"Protein: {data.get('name', 'Unknown')}\nMW: {data.get('mw_kda', 0.0):.2f} kDa")
        info_label.setStyleSheet(get_label_style())
        layout.addWidget(info_label)
        
        role_label = QLabel("Assign as:")
        role_label.setStyleSheet(get_label_style())
        layout.addWidget(role_label)
        
        role_combo = QComboBox()
        role_combo.addItems(["Ligand", "Target"])
        role_combo.setStyleSheet(get_combobox_style())
        layout.addWidget(role_combo)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec() == QDialog.Accepted:
            role = role_combo.currentText()
            if role == "Ligand":
                self.ligand_name_display.setText(data.get('name', 'Unknown'))
                self.ligand_mw_input.setValue(data.get('mw_kda', 0.0))
            else:
                self.target_name_display.setText(data.get('name', 'Unknown'))
                self.target_mw_input.setValue(data.get('mw_kda', 0.0))
            
            self.protein_uniprot_input.clear()
            self._update_summary_table()
    
    @Slot(str)
    def _handle_lookup_error(self, error_msg: str):
        """Handle lookup error"""
        self.protein_lookup_btn.setEnabled(True)
        self.protein_lookup_btn.setText("Lookup")
        QMessageBox.critical(self, "Lookup Failed", f"Error: {error_msg}")
    
    def _search_protein_inline(self):
        """Search database and show results inline"""
        query = self.protein_name_input.text().strip()
        if not query:
            QMessageBox.warning(self, "Missing Query", "Please enter a protein name")
            return
        
        organism = self.organism_combo.currentText().lower()
        if organism == "any":
            organism = ""
        
        self.protein_search_btn.setEnabled(False)
        self.protein_search_btn.setText("Searching...")
        self.search_results_list.clear()
        
        self.search_thread = UniProtSearchThread(query, organism)
        self.search_thread.finished.connect(self._show_search_results)
        self.search_thread.error.connect(self._handle_search_error)
        self.search_thread.start()
    
    @Slot(list)
    def _show_search_results(self, results: list):
        """Display search results inline"""
        self.protein_search_btn.setEnabled(True)
        self.protein_search_btn.setText("Search")
        
        if not results:
            self.current_protein_label.setText("No results found")
            self.search_results_list.hide()
            return
        
        self.search_results_list.clear()
        for protein in results[:10]:  # Limit to 10 results
            name = protein.get('name', 'Unknown')
            uniprot_id = protein.get('uniprot_id', '')
            mw = protein.get('mw_kda', 0.0)
            item_text = f"{name} ({uniprot_id}) - {mw:.1f} kDa"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, protein)
            self.search_results_list.addItem(item)
        
        self.search_results_list.show()
        self.current_protein_label.setText(f"Found {len(results)} results - click to select")
    
    @Slot(str)
    def _handle_search_error(self, error_msg: str):
        """Handle search error"""
        self.protein_search_btn.setEnabled(True)
        self.protein_search_btn.setText("Search")
        self.current_protein_label.setText(f"Search error: {error_msg}")
        self.search_results_list.hide()
    
    def _select_search_result(self, item):
        """Select a protein from search results"""
        protein = item.data(Qt.UserRole)
        if protein:
            self.current_protein_data = protein
            self.current_protein_label.setText(f"Selected: {protein.get('name', 'Unknown')} ({protein.get('mw_kda', 0.0):.1f} kDa) - Click tag to assign")
    
    def _show_custom_proteins(self):
        """Show custom proteins in the search results list"""
        if not self.custom_proteins:
            self.current_protein_label.setText("No custom proteins - use Proteins menu to add")
            self.search_results_list.hide()
            return
        
        self.search_results_list.clear()
        for protein in self.custom_proteins:
            name = protein.get('name', 'Unknown')
            mw = protein.get('mw_kda', 0.0)
            item_text = f"{name} - {mw:.1f} kDa [Custom]"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, protein)
            self.search_results_list.addItem(item)
        
        self.search_results_list.show()
        self.current_protein_label.setText(f"Showing {len(self.custom_proteins)} custom proteins - click to select")
    
    def _search_protein_with_role(self):
        """Search database and store result"""
        dialog = ProteinSearchDialog(self)
        if dialog.exec() == QDialog.Accepted and dialog.selected_protein:
            protein = dialog.selected_protein
            
            self.current_protein_data = protein
            self.current_protein_label.setText(f"Found: {protein.get('name', 'Unknown')} ({protein.get('mw_kda', 0.0):.1f} kDa) - Click tag to assign")
    
    def _get_protein_by_role(self, role: str) -> tuple:
        """Get protein data by role"""
        if role == "Analyte" or role == "Target":
            name = self.current_protein_label.text() if hasattr(self, 'current_protein_data') and self.current_protein_data else ""
            if "assigned to Target" in name:
                name = name.split(" assigned")[0]
            elif "Found:" in name:
                name = ""
            return (name, self.target_mw_input.value())
        else:  # Ligand
            name = self.current_protein_label.text() if hasattr(self, 'current_protein_data') and self.current_protein_data else ""
            if "assigned to Ligand" in name:
                name = name.split(" assigned")[0]
            elif "Found:" in name:
                name = ""
            return (name, self.ligand_mw_input.value())
    
    def _create_summary_table(self) -> QGroupBox:
        """Create experiment summary table"""
        group = QGroupBox("Experiment Summary")
        group.setStyleSheet(get_groupbox_style())
        layout = QVBoxLayout()
        layout.setSpacing(8)
        
        # Summary table
        self.summary_table = QTableWidget()
        self.summary_table.setColumnCount(2)
        self.summary_table.setHorizontalHeaderLabels(["Parameter", "Value"])
        self.summary_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.summary_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.summary_table.verticalHeader().setVisible(False)
        self.summary_table.setMaximumHeight(250)
        self.summary_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.OUTLINE};
                border-radius: 4px;
                gridline-color: {Colors.OUTLINE};
                font-family: {Typography.FAMILY};
                font-size: 9pt;
            }}
            QHeaderView::section {{
                background-color: {Colors.GRAY_50};
                color: {Colors.GRAY_900};
                font-weight: 600;
                font-size: 9pt;
                border: none;
                border-bottom: 1px solid {Colors.OUTLINE};
                padding: 4px 8px;
            }}
            QTableWidget::item {{
                padding: 4px 8px;
            }}
        """)
        
        # Initialize rows
        self.summary_table.setRowCount(5)
        
        self.summary_table.setItem(0, 0, QTableWidgetItem("Ligand (Surface)"))
        self.summary_table.setItem(1, 0, QTableWidgetItem("Target (Solution)"))
        self.summary_table.setItem(2, 0, QTableWidgetItem("MW Ratio (Solution/Surface)"))
        self.summary_table.setItem(3, 0, QTableWidgetItem("Immobilization (RU)"))
        self.summary_table.setItem(4, 0, QTableWidgetItem("Theoretical Rmax (RU)"))
        
        for row in range(5):
            self.summary_table.setItem(row, 1, QTableWidgetItem("—"))
        
        layout.addWidget(self.summary_table)
        
        group.setLayout(layout)
        return group
    
    def _update_summary_table(self):
        """Update the summary table with current values"""
        ligand_name, mw_ligand = self._get_protein_by_role("Ligand")
        target_name, mw_target = self._get_protein_by_role("Target")
        
        # Ligand info
        if ligand_name and ligand_name != "—":
            self.summary_table.setItem(0, 1, QTableWidgetItem(f"{ligand_name} ({mw_ligand:.2f} kDa)"))
        else:
            self.summary_table.setItem(0, 1, QTableWidgetItem("—"))
        
        # Target info
        if target_name and target_name != "—":
            self.summary_table.setItem(1, 1, QTableWidgetItem(f"{target_name} ({mw_target:.2f} kDa)"))
        else:
            self.summary_table.setItem(1, 1, QTableWidgetItem("—"))
        
        # MW Ratio
        if mw_ligand > 0 and mw_target > 0:
            mw_ratio = mw_target / mw_ligand
            self.summary_table.setItem(2, 1, QTableWidgetItem(f"{mw_ratio:.3f}"))
        else:
            self.summary_table.setItem(2, 1, QTableWidgetItem("—"))
        
        # Immobilization
        r_ligand = self.immobilization_input.value()
        self.summary_table.setItem(3, 1, QTableWidgetItem(f"{r_ligand:.1f}"))
        
        # Theoretical Rmax
        if mw_ligand > 0 and mw_target > 0 and r_ligand > 0:
            stoich = self.stoichiometry_input.value()
            rmax = calculate_theoretical_rmax(mw_target, mw_ligand, r_ligand, stoich)
            self.summary_table.setItem(4, 1, QTableWidgetItem(f"{rmax:.1f}"))
        else:
            self.summary_table.setItem(4, 1, QTableWidgetItem("—"))
    
    def _create_parameters_section(self) -> QGroupBox:
        grid.setSpacing(12)
        
        # Ligand column
        ligand_layout = QVBoxLayout()
        ligand_layout.setSpacing(6)
        
        ligand_header = QLabel("Ligand (Immobilized)")
        ligand_header.setStyleSheet(f"""
            QLabel {{
                font-size: 11px;
                font-weight: 600;
                color: {Colors.GRAY_500};
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
        """)
        ligand_layout.addWidget(ligand_header)
        
        # UniProt ID input
        uniprot_ligand_layout = QHBoxLayout()
        uniprot_ligand_label = QLabel("UniProt ID:")
        uniprot_ligand_label.setMinimumWidth(80)
        uniprot_ligand_label.setStyleSheet(get_label_style())
        self.ligand_uniprot_input = QLineEdit()
        self.ligand_uniprot_input.setPlaceholderText("e.g., P01375")
        self.ligand_uniprot_input.setStyleSheet(get_input_style())
        uniprot_ligand_layout.addWidget(uniprot_ligand_label)
        uniprot_ligand_layout.addWidget(self.ligand_uniprot_input, 1)
        ligand_layout.addLayout(uniprot_ligand_layout)
        
        # Buttons
        ligand_btn_layout = QHBoxLayout()
        ligand_btn_layout.setSpacing(6)
        self.ligand_lookup_btn = QPushButton("Lookup")
        self.ligand_lookup_btn.setStyleSheet(get_button_style("primary"))
        self.ligand_search_btn = QPushButton("Search")
        self.ligand_search_btn.setStyleSheet(get_button_style("standard"))
        self.ligand_load_custom_btn = QPushButton("Load Custom")
        self.ligand_load_custom_btn.setStyleSheet(get_button_style("standard"))
        self.ligand_lookup_btn.clicked.connect(lambda: self._lookup_protein("ligand"))
        self.ligand_search_btn.clicked.connect(lambda: self._search_protein("ligand"))
        self.ligand_load_custom_btn.clicked.connect(lambda: self._load_custom_protein("ligand"))
        ligand_btn_layout.addWidget(self.ligand_lookup_btn)
        ligand_btn_layout.addWidget(self.ligand_search_btn)
        ligand_btn_layout.addWidget(self.ligand_load_custom_btn)
        ligand_layout.addLayout(ligand_btn_layout)
        
        # Name display
        name_ligand_layout = QHBoxLayout()
        name_ligand_label = QLabel("Name:")
        name_ligand_label.setMinimumWidth(80)
        name_ligand_label.setStyleSheet(get_label_style())
        self.ligand_name_display = QLineEdit()
        self.ligand_name_display.setReadOnly(True)
        self.ligand_name_display.setPlaceholderText("—")
        self.ligand_name_display.setStyleSheet(get_input_style())
        name_ligand_layout.addWidget(name_ligand_label)
        name_ligand_layout.addWidget(self.ligand_name_display, 1)
        ligand_layout.addLayout(name_ligand_layout)
        
        # MW
        mw_ligand_layout = QHBoxLayout()
        mw_ligand_label = QLabel("MW (kDa):")
        mw_ligand_label.setMinimumWidth(80)
        mw_ligand_label.setStyleSheet(get_label_style())
        self.ligand_mw_input = QDoubleSpinBox()
        self.ligand_mw_input.setRange(0.1, 10000.0)
        self.ligand_mw_input.setDecimals(2)
        self.ligand_mw_input.setValue(150.0)
        self.ligand_mw_input.setStyleSheet(get_input_style())
        mw_ligand_layout.addWidget(mw_ligand_label)
        mw_ligand_layout.addWidget(self.ligand_mw_input, 1)
        ligand_layout.addLayout(mw_ligand_layout)
        
        grid.addLayout(ligand_layout, 1)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setStyleSheet(f"background-color: {Colors.OUTLINE};")
        separator.setMaximumWidth(1)
        grid.addWidget(separator)
        
        # Analyte column
        analyte_layout = QVBoxLayout()
        analyte_layout.setSpacing(6)
        
        analyte_header = QLabel("Analyte (In Solution)")
        analyte_header.setStyleSheet(f"""
            QLabel {{
                font-size: 11px;
                font-weight: 600;
                color: {Colors.GRAY_500};
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
        """)
        analyte_layout.addWidget(analyte_header)
        
        # UniProt ID
        uniprot_analyte_layout = QHBoxLayout()
        uniprot_analyte_label = QLabel("UniProt ID:")
        uniprot_analyte_label.setMinimumWidth(80)
        uniprot_analyte_label.setStyleSheet(get_label_style())
        self.analyte_uniprot_input = QLineEdit()
        self.analyte_uniprot_input.setPlaceholderText("e.g., P01375")
        self.analyte_uniprot_input.setStyleSheet(get_input_style())
        uniprot_analyte_layout.addWidget(uniprot_analyte_label)
        uniprot_analyte_layout.addWidget(self.analyte_uniprot_input, 1)
        analyte_layout.addLayout(uniprot_analyte_layout)
        
        # Buttons
        analyte_btn_layout = QHBoxLayout()
        analyte_btn_layout.setSpacing(6)
        self.analyte_lookup_btn = QPushButton("Lookup")
        self.analyte_lookup_btn.setStyleSheet(get_button_style("primary"))
        self.analyte_search_btn = QPushButton("Search")
        self.analyte_search_btn.setStyleSheet(get_button_style("standard"))
        self.analyte_load_custom_btn = QPushButton("Load Custom")
        self.analyte_load_custom_btn.setStyleSheet(get_button_style("standard"))
        self.analyte_lookup_btn.clicked.connect(lambda: self._lookup_protein("analyte"))
        self.analyte_search_btn.clicked.connect(lambda: self._search_protein("analyte"))
        self.analyte_load_custom_btn.clicked.connect(lambda: self._load_custom_protein("analyte"))
        analyte_btn_layout.addWidget(self.analyte_lookup_btn)
        analyte_btn_layout.addWidget(self.analyte_search_btn)
        analyte_btn_layout.addWidget(self.analyte_load_custom_btn)
        analyte_layout.addLayout(analyte_btn_layout)
        
        # Name
        name_analyte_layout = QHBoxLayout()
        name_analyte_label = QLabel("Name:")
        name_analyte_label.setMinimumWidth(80)
        name_analyte_label.setStyleSheet(get_label_style())
        self.analyte_name_display = QLineEdit()
        self.analyte_name_display.setReadOnly(True)
        self.analyte_name_display.setPlaceholderText("—")
        self.analyte_name_display.setStyleSheet(get_input_style())
        name_analyte_layout.addWidget(name_analyte_label)
        name_analyte_layout.addWidget(self.analyte_name_display, 1)
        analyte_layout.addLayout(name_analyte_layout)
        
        # MW
        mw_analyte_layout = QHBoxLayout()
        mw_analyte_label = QLabel("MW (kDa):")
        mw_analyte_label.setMinimumWidth(80)
        mw_analyte_label.setStyleSheet(get_label_style())
        self.analyte_mw_input = QDoubleSpinBox()
        self.analyte_mw_input.setRange(0.1, 10000.0)
        self.analyte_mw_input.setDecimals(2)
        self.analyte_mw_input.setValue(50.0)
        self.analyte_mw_input.setStyleSheet(get_input_style())
        mw_analyte_layout.addWidget(mw_analyte_label)
        mw_analyte_layout.addWidget(self.analyte_mw_input, 1)
        analyte_layout.addLayout(mw_analyte_layout)
        
        grid.addLayout(analyte_layout, 1)
        
        layout.addLayout(grid)
        group.setLayout(layout)
        return group
    
    def _create_experiment_parameters(self) -> QGroupBox:
        """Create experiment parameters section"""
        group = QGroupBox("Experiment Parameters")
        group.setStyleSheet(get_groupbox_style())
        layout = QVBoxLayout()
        layout.setSpacing(6)
        
        # Three-column layout
        params_layout = QHBoxLayout()
        params_layout.setSpacing(8)
        
        # Column 1: Stoichiometry
        col1_layout = QVBoxLayout()
        stoich_label = QLabel("Stoichiometry:")
        stoich_label.setStyleSheet(get_label_style(bold=True))
        self.stoichiometry_input = QSpinBox()
        self.stoichiometry_input.setRange(1, 10)
        self.stoichiometry_input.setValue(1)
        self.stoichiometry_input.setStyleSheet(get_input_style())
        self.stoichiometry_input.valueChanged.connect(self._update_summary_table)
        col1_layout.addWidget(stoich_label)
        col1_layout.addWidget(self.stoichiometry_input)
        col1_layout.addStretch()
        params_layout.addLayout(col1_layout)
        
        # Column 2: KD
        col2_layout = QVBoxLayout()
        kd_label = QLabel("Expected K<sub>D</sub>:")
        kd_label.setStyleSheet(get_label_style(bold=True))
        kd_row = QHBoxLayout()
        self.kd_value_input = QDoubleSpinBox()
        self.kd_value_input.setRange(0.001, 100000.0)
        self.kd_value_input.setDecimals(3)
        self.kd_value_input.setValue(10.0)
        self.kd_value_input.setStyleSheet(get_input_style())
        self.kd_unit_combo = QComboBox()
        self.kd_unit_combo.addItems(["nM", "µM", "mM", "M"])
        self.kd_unit_combo.setCurrentText("nM")
        self.kd_unit_combo.setStyleSheet(get_combobox_style())
        kd_row.addWidget(self.kd_value_input, 2)
        kd_row.addWidget(self.kd_unit_combo, 1)
        col2_layout.addWidget(kd_label)
        col2_layout.addLayout(kd_row)
        col2_layout.addStretch()
        params_layout.addLayout(col2_layout)
        
        # Column 3: Immobilization
        col3_layout = QVBoxLayout()
        immob_label = QLabel("Immobilization Level:")
        immob_label.setStyleSheet(get_label_style(bold=True))
        immob_row = QHBoxLayout()
        self.immobilization_input = QDoubleSpinBox()
        self.immobilization_input.setRange(0, 50000.0)
        self.immobilization_input.setDecimals(1)
        self.immobilization_input.setValue(500.0)
        self.immobilization_input.setStyleSheet(get_input_style())
        self.immobilization_input.valueChanged.connect(self._update_summary_table)
        immob_unit = QLabel("RU")
        immob_unit.setStyleSheet(get_label_style())
        immob_row.addWidget(self.immobilization_input, 2)
        immob_row.addWidget(immob_unit, 1)
        col3_layout.addWidget(immob_label)
        col3_layout.addLayout(immob_row)
        col3_layout.addStretch()
        params_layout.addLayout(col3_layout)
        
        layout.addLayout(params_layout)
        group.setLayout(layout)
        return group
    
    def _create_calculation_section(self) -> QGroupBox:
        """Create theoretical calculations section"""
        group = QGroupBox("Theoretical Calculations")
        group.setStyleSheet(get_groupbox_style())
        layout = QVBoxLayout()
        layout.setSpacing(6)
        
        # Calculate button
        calc_btn = QPushButton("Calculate Expected Rmax")
        calc_btn.setStyleSheet(get_button_style("success"))
        calc_btn.clicked.connect(self._update_calculations)
        layout.addWidget(calc_btn)
        
        # Results display
        results_frame = QFrame()
        results_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.GRAY_50};
                border: 1px solid {Colors.OUTLINE};
                border-radius: 4px;
                padding: 8px;
            }}
        """)
        results_layout = QVBoxLayout(results_frame)
        results_layout.setSpacing(4)
        
        self.theoretical_rmax_label = QLabel("Theoretical R<sub>max</sub>: —")
        self.theoretical_rmax_label.setStyleSheet(f"""
            QLabel {{
                font-family: {Typography.FAMILY};
                font-size: 11px;
                font-weight: 600;
                color: {Colors.GRAY_900};
            }}
        """)
        
        self.rmax_interpretation_label = QLabel("")
        self.rmax_interpretation_label.setWordWrap(True)
        self.rmax_interpretation_label.setStyleSheet(get_label_style())
        
        results_layout.addWidget(self.theoretical_rmax_label)
        results_layout.addWidget(self.rmax_interpretation_label)
        
        layout.addWidget(results_frame)
        group.setLayout(layout)
        return group
    
    def _create_concentration_series(self) -> QGroupBox:
        """Create concentration series planning section"""
        group = QGroupBox("Concentration Series Design")
        group.setStyleSheet(get_groupbox_style())
        layout = QVBoxLayout()
        layout.setSpacing(6)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        num_points_label = QLabel("Number of Points:")
        num_points_label.setStyleSheet(get_label_style(bold=True))
        self.num_points_input = QSpinBox()
        self.num_points_input.setRange(3, 12)
        self.num_points_input.setValue(7)
        self.num_points_input.setStyleSheet(get_input_style())
        
        generate_btn = QPushButton("Generate Series")
        generate_btn.setStyleSheet(get_button_style("primary"))
        generate_btn.clicked.connect(self._generate_concentration_series)
        
        export_btn = QPushButton("Copy to Clipboard")
        export_btn.setStyleSheet(get_button_style("standard"))
        export_btn.clicked.connect(self._export_concentration_table)
        
        controls_layout.addWidget(num_points_label)
        controls_layout.addWidget(self.num_points_input)
        controls_layout.addStretch()
        controls_layout.addWidget(generate_btn)
        controls_layout.addWidget(export_btn)
        
        layout.addLayout(controls_layout)
        
        # Concentration table
        self.concentration_table = QTableWidget()
        self.concentration_table.setColumnCount(5)
        self.concentration_table.setHorizontalHeaderLabels([
            "Conc (nM)", "Conc (µg/mL)", "C/K<sub>D</sub>", "Expected RU", "% R<sub>max</sub>"
        ])
        self.concentration_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.concentration_table.setMaximumHeight(250)
        self.concentration_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Colors.SURFACE};
                border: 1px solid {Colors.OUTLINE};
                border-radius: {Radius.SM}px;
                gridline-color: {Colors.OUTLINE};
                font-family: {Typography.FAMILY};
                font-size: 9pt;
            }}
            QHeaderView::section {{
                background-color: {Colors.GRAY_50};
                color: {Colors.GRAY_900};
                font-weight: 600;
                font-size: 9pt;
                border: none;
                border-bottom: 1px solid {Colors.OUTLINE};
                padding: 4px 8px;
            }}
            QTableWidget::item {{
                padding: 4px 8px;
            }}
        """)
        
        layout.addWidget(self.concentration_table)
        group.setLayout(layout)
        return group
    
    def _create_validation_section(self) -> QGroupBox:
        """Create experimental validation section"""
        group = QGroupBox("Experimental Validation")
        group.setStyleSheet(get_groupbox_style())
        layout = QVBoxLayout()
        layout.setSpacing(6)
        
        # Input fields
        inputs_layout = QHBoxLayout()
        
        # Experimental Rmax
        exp_rmax_layout = QVBoxLayout()
        exp_rmax_label = QLabel("Experimental R<sub>max</sub> (RU):")
        exp_rmax_label.setStyleSheet(get_label_style(bold=True))
        self.exp_rmax_input = QDoubleSpinBox()
        self.exp_rmax_input.setRange(0, 50000.0)
        self.exp_rmax_input.setDecimals(1)
        self.exp_rmax_input.setValue(0.0)
        self.exp_rmax_input.setStyleSheet(get_input_style())
        exp_rmax_layout.addWidget(exp_rmax_label)
        exp_rmax_layout.addWidget(self.exp_rmax_input)
        inputs_layout.addLayout(exp_rmax_layout)
        
        # Calculate button
        validate_btn_layout = QVBoxLayout()
        validate_btn_layout.addStretch()
        validate_btn = QPushButton("Calculate Surface Activity")
        validate_btn.setStyleSheet(get_button_style("primary"))
        validate_btn.clicked.connect(self._calculate_surface_activity)
        validate_btn_layout.addWidget(validate_btn)
        inputs_layout.addLayout(validate_btn_layout)
        
        layout.addLayout(inputs_layout)
        
        # Results
        results_frame = QFrame()
        results_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.GRAY_50};
                border: 1px solid {Colors.OUTLINE};
                border-radius: 4px;
                padding: 8px;
            }}
        """)
        results_layout = QVBoxLayout(results_frame)
        results_layout.setSpacing(4)
        
        self.surface_activity_label = QLabel("Surface Activity: —")
        self.surface_activity_label.setStyleSheet(f"""
            QLabel {{
                font-family: {Typography.FAMILY};
                font-size: 11px;
                font-weight: 600;
                color: {Colors.GRAY_900};
            }}
        """)
        
        self.activity_interpretation_label = QLabel("")
        self.activity_interpretation_label.setWordWrap(True)
        self.activity_interpretation_label.setStyleSheet(get_label_style())
        
        results_layout.addWidget(self.surface_activity_label)
        results_layout.addWidget(self.activity_interpretation_label)
        
        layout.addWidget(results_frame)
        group.setLayout(layout)
        return group
    
    # ========================================================================
    # CALCULATION METHODS
    # ========================================================================
    
    def _update_calculations(self):
        """Calculate theoretical Rmax"""
        analyte_name, mw_analyte = self._get_protein_by_role("Analyte")
        ligand_name, mw_ligand = self._get_protein_by_role("Ligand")
        r_ligand = self.immobilization_input.value()
        stoich = self.stoichiometry_input.value()
        
        if mw_analyte <= 0 or mw_ligand <= 0 or r_ligand <= 0:
            self.theoretical_rmax_label.setText("Theoretical R<sub>max</sub>: —")
            self.rmax_interpretation_label.setText("⚠️ Enter all parameters")
            return
        
        # Calculate theoretical Rmax
        rmax = (mw_analyte / mw_ligand) * r_ligand * stoich
        
        self.theoretical_rmax_label.setText(f"Theoretical R<sub>max</sub>: {rmax:.1f} RU")
        
        # Interpretation
        if rmax < 50:
            color = Colors.WARNING
            msg = "⚠️ Low signal expected. Consider increasing immobilization level or using higher MW analyte."
        elif rmax > 1000:
            color = Colors.WARNING
            msg = "⚠️ High signal. May encounter mass transport limitations. Consider reducing immobilization."
        else:
            color = Colors.SUCCESS
            msg = "✓ Good signal range for SPR experiments (50-1000 RU)."
        
        self.rmax_interpretation_label.setText(msg)
        self.rmax_interpretation_label.setStyleSheet(f"""
            QLabel {{
                font-family: {Typography.FAMILY};
                font-size: 9pt;
                color: {color};
            }}
        """)
    
    def _generate_concentration_series(self):
        """Generate concentration series based on KD"""
        num_points = self.num_points_input.value()
        kd_value = self.kd_value_input.value()
        kd_unit = self.kd_unit_combo.currentText()
        
        # Convert KD to M
        kd_m = self._convert_to_molar(kd_value, kd_unit)
        
        # Generate logarithmic series from 0.1×KD to 10×KD
        import numpy as np
        concentrations_m = np.logspace(
            np.log10(kd_m * 0.1),
            np.log10(kd_m * 10),
            num_points
        )
        
        # Get MW and Rmax for conversion and response calculation
        analyte_name, mw_analyte = self._get_protein_by_role("Analyte")
        ligand_name, mw_ligand = self._get_protein_by_role("Ligand")
        r_ligand = self.immobilization_input.value()
        stoich = self.stoichiometry_input.value()
        
        if mw_ligand > 0 and r_ligand > 0:
            rmax = (mw_analyte / mw_ligand) * r_ligand * stoich
        else:
            rmax = 0
        
        # Populate table
        self.concentration_table.setRowCount(num_points)
        
        for i, conc_m in enumerate(concentrations_m):
            # Convert to nM
            conc_nm = conc_m * 1e9
            
            # Convert to µg/mL
            conc_ug_ml = (conc_m * 1000) * (mw_analyte * 1000) if mw_analyte > 0 else 0
            
            # C/KD ratio
            c_kd_ratio = conc_m / kd_m if kd_m > 0 else 0
            
            # Expected response (Langmuir)
            if rmax > 0 and kd_m > 0:
                expected_ru = rmax * (conc_m / (conc_m + kd_m))
                percent_rmax = (expected_ru / rmax) * 100
            else:
                expected_ru = 0
                percent_rmax = 0
            
            # Add to table
            self.concentration_table.setItem(i, 0, QTableWidgetItem(f"{conc_nm:.3f}"))
            self.concentration_table.setItem(i, 1, QTableWidgetItem(f"{conc_ug_ml:.3f}"))
            self.concentration_table.setItem(i, 2, QTableWidgetItem(f"{c_kd_ratio:.2f}"))
            self.concentration_table.setItem(i, 3, QTableWidgetItem(f"{expected_ru:.1f}"))
            self.concentration_table.setItem(i, 4, QTableWidgetItem(f"{percent_rmax:.1f}"))
            
            # Color coding
            if percent_rmax < 20:
                bg_color = QColor(Colors.ERROR).lighter(180)
            elif percent_rmax > 80:
                bg_color = QColor(Colors.WARNING).lighter(180)
            else:
                bg_color = QColor(Colors.SUCCESS).lighter(180)
            
            for col in range(5):
                self.concentration_table.item(i, col).setBackground(bg_color)
    
    def _calculate_surface_activity(self):
        """Calculate surface activity percentage"""
        exp_rmax = self.exp_rmax_input.value()
        
        # Get theoretical Rmax
        analyte_name, mw_analyte = self._get_protein_by_role("Analyte")
        ligand_name, mw_ligand = self._get_protein_by_role("Ligand")
        r_ligand = self.immobilization_input.value()
        stoich = self.stoichiometry_input.value()
        
        if mw_ligand > 0 and r_ligand > 0:
            theo_rmax = (mw_analyte / mw_ligand) * r_ligand * stoich
        else:
            self.surface_activity_label.setText("Surface Activity: —")
            self.activity_interpretation_label.setText("⚠️ Calculate theoretical Rmax first")
            return
        
        if theo_rmax <= 0:
            return
        
        activity_percent = (exp_rmax / theo_rmax) * 100
        
        self.surface_activity_label.setText(f"Surface Activity: {activity_percent:.1f}%")
        
        # Interpretation
        if 80 <= activity_percent <= 110:
            color = Colors.SUCCESS
            msg = "✓ Excellent! Surface is highly active with proper orientation."
        elif 50 <= activity_percent < 80:
            color = Colors.WARNING
            msg = "⚠️ Moderate activity. Possible orientation issues or partial denaturation."
        elif activity_percent < 50:
            color = Colors.ERROR
            msg = "❌ Low activity. Check immobilization method, protein stability, or surface preparation."
        else:
            color = Colors.WARNING
            msg = "⚠️ >100% activity. Check for avidity effects, aggregation, or measurement errors."
        
        self.activity_interpretation_label.setText(msg)
        self.activity_interpretation_label.setStyleSheet(f"""
            QLabel {{
                font-family: {Typography.FAMILY};
                font-size: 9pt;
                color: {color};
            }}
        """)
    
    def _convert_to_molar(self, value: float, unit: str) -> float:
        """Convert concentration to molar"""
        conversions = {
            "M": 1.0,
            "mM": 1e-3,
            "µM": 1e-6,
            "nM": 1e-9,
        }
        return value * conversions.get(unit, 1.0)
    
    def _export_concentration_table(self):
        """Copy concentration table to clipboard"""
        if self.concentration_table.rowCount() == 0:
            return
        
        # Build TSV string
        headers = [
            self.concentration_table.horizontalHeaderItem(i).text()
            for i in range(self.concentration_table.columnCount())
        ]
        lines = ["\t".join(headers)]
        
        for row in range(self.concentration_table.rowCount()):
            row_data = [
                self.concentration_table.item(row, col).text()
                for col in range(self.concentration_table.columnCount())
            ]
            lines.append("\t".join(row_data))
        
        QApplication.clipboard().setText("\n".join(lines))
        QMessageBox.information(self, "Exported", "Concentration series copied to clipboard!")
    
    # ========================================================================
    # FILE OPERATIONS
    # ========================================================================
    
    def _new_experiment(self):
        """Clear all fields for new experiment"""
        reply = QMessageBox.question(
            self, "New Experiment",
            "Clear all fields and start a new experiment?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.protein_uniprot_input.clear()
            self.current_protein_data = None
            self.current_protein_label.setText("No protein selected")
            self.ligand_mw_input.setValue(150.0)
            self.target_mw_input.setValue(50.0)
            
            self.stoichiometry_input.setValue(1)
            self.kd_value_input.setValue(10.0)
            self.kd_unit_combo.setCurrentText("nM")
            self.immobilization_input.setValue(1000.0)
            
            self.theoretical_rmax_label.setText("Theoretical R<sub>max</sub>: —")
            self.rmax_interpretation_label.setText("")
            
            self.concentration_table.setRowCount(0)
            
            self.exp_rmax_input.setValue(0.0)
            self.surface_activity_label.setText("Surface Activity: —")
            self.activity_interpretation_label.setText("")
            
            self.current_experiment_file = None
            self.setWindowTitle("SPR Experiment Planner - AffiLabs")
    
    def _save_experiment(self, save_as: bool = False):
        """Save current experiment to JSON"""
        if save_as or not self.current_experiment_file:
            self.experiments_dir.mkdir(parents=True, exist_ok=True)
            default_name = f"experiment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Experiment",
                str(self.experiments_dir / default_name),
                "JSON Files (*.json)"
            )
            
            if not file_path:
                return
            
            self.current_experiment_file = Path(file_path)
        
        self._save_experiment_to_file(self.current_experiment_file)
        self.setWindowTitle(f"SPR Experiment Planner - {self.current_experiment_file.name}")
        QMessageBox.information(self, "Saved", f"Experiment saved to {self.current_experiment_file.name}")
    
    def _save_experiment_to_file(self, file_path: Path):
        """Save experiment data to file"""
        data = {
            "version": "2.0",
            "created": datetime.now().isoformat(),
            "ligand": {
                "uniprot_id": self.ligand_uniprot_input.text(),
                "name": self.ligand_name_display.text(),
                "mw_kda": self.ligand_mw_input.value(),
            },
            "analyte": {
                "uniprot_id": self.analyte_uniprot_input.text(),
                "name": self.analyte_name_display.text(),
                "mw_kda": self.analyte_mw_input.value(),
            },
            "parameters": {
                "stoichiometry": self.stoichiometry_input.value(),
                "kd_value": self.kd_value_input.value(),
                "kd_unit": self.kd_unit_combo.currentText(),
                "immobilization": self.immobilization_input.value(),
            }
        }
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _load_experiment(self):
        """Load experiment from JSON"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Experiment",
            str(self.experiments_dir),
            "JSON Files (*.json)"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Load ligand data
            ligand = data.get('ligand', {})
            self.ligand_uniprot_input.setText(ligand.get('uniprot_id', ''))
            self.ligand_name_display.setText(ligand.get('name', '—'))
            self.ligand_mw_input.setValue(ligand.get('mw_kda', 150.0))
            
            # Load analyte data
            analyte = data.get('analyte', {})
            self.analyte_uniprot_input.setText(analyte.get('uniprot_id', ''))
            self.analyte_name_display.setText(analyte.get('name', '—'))
            self.analyte_mw_input.setValue(analyte.get('mw_kda', 50.0))
            
            # Load parameters
            params = data.get('parameters', {})
            self.stoichiometry_input.setValue(params.get('stoichiometry', 1))
            self.kd_value_input.setValue(params.get('kd_value', 10.0))
            self.kd_unit_combo.setCurrentText(params.get('kd_unit', 'nM'))
            self.immobilization_input.setValue(params.get('immobilization', 1000.0))
            
            self.current_experiment_file = Path(file_path)
            self.setWindowTitle(f"SPR Experiment Planner - {self.current_experiment_file.name}")
            
            # Update calculations
            self._update_calculations()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load experiment:\n{str(e)}")
    
    def _export_report(self):
        """Export experiment report as text file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Report",
            str(Path.home() / "spr_experiment_report.txt"),
            "Text Files (*.txt)"
        )
        
        if not file_path:
            return
        
        # Generate report
        report = [
            "SPR EXPERIMENT PLANNING REPORT",
            "=" * 60,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "PROTEIN INFORMATION",
            "-" * 60,
            f"Ligand: {self.ligand_name_display.text()}",
            f"  UniProt ID: {self.ligand_uniprot_input.text()}",
            f"  MW: {self.ligand_mw_input.value():.2f} kDa",
            "",
            f"Analyte: {self.analyte_name_display.text()}",
            f"  UniProt ID: {self.analyte_uniprot_input.text()}",
            f"  MW: {self.analyte_mw_input.value():.2f} kDa",
            "",
            "EXPERIMENT PARAMETERS",
            "-" * 60,
            f"Stoichiometry: {self.stoichiometry_input.value()}:1",
            f"Expected KD: {self.kd_value_input.value()} {self.kd_unit_combo.currentText()}",
            f"Immobilization: {self.immobilization_input.value():.1f} RU",
            "",
            "THEORETICAL CALCULATIONS",
            "-" * 60,
            self.theoretical_rmax_label.text().replace("<sub>", "").replace("</sub>", ""),
            self.rmax_interpretation_label.text(),
            "",
        ]
        
        with open(file_path, 'w') as f:
            f.write("\n".join(report))
        
        QMessageBox.information(self, "Exported", f"Report saved to {Path(file_path).name}")
    
    # ========================================================================
    # CUSTOM PROTEIN LIBRARY
    # ========================================================================
    
    def _load_custom_proteins(self) -> List[Dict[str, Any]]:
        """Load custom proteins from JSON file"""
        if not self.custom_proteins_file.exists():
            return []
        
        try:
            with open(self.custom_proteins_file, 'r') as f:
                return json.load(f)
        except:
            return []
    
    def _save_custom_proteins(self):
        """Save custom proteins to JSON file"""
        self.custom_proteins_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.custom_proteins_file, 'w') as f:
            json.dump(self.custom_proteins, f, indent=2)
    
    def _add_custom_protein(self):
        """Add custom protein to library"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Custom Protein")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(Spacing.MD)
        
        # Name
        name_layout = QHBoxLayout()
        name_label = QLabel("Name:")
        name_label.setMinimumWidth(100)
        name_input = QLineEdit()
        name_input.setStyleSheet(get_input_style())
        name_layout.addWidget(name_label)
        name_layout.addWidget(name_input)
        layout.addLayout(name_layout)
        
        # MW
        mw_layout = QHBoxLayout()
        mw_label = QLabel("MW (kDa):")
        mw_label.setMinimumWidth(100)
        mw_input = QDoubleSpinBox()
        mw_input.setRange(0.1, 10000.0)
        mw_input.setDecimals(2)
        mw_input.setStyleSheet(get_input_style())
        mw_layout.addWidget(mw_label)
        mw_layout.addWidget(mw_input)
        layout.addLayout(mw_layout)
        
        # UniProt ID (optional)
        uniprot_layout = QHBoxLayout()
        uniprot_label = QLabel("UniProt ID:")
        uniprot_label.setMinimumWidth(100)
        uniprot_input = QLineEdit()
        uniprot_input.setPlaceholderText("Optional")
        uniprot_input.setStyleSheet(get_input_style())
        uniprot_layout.addWidget(uniprot_label)
        uniprot_layout.addWidget(uniprot_input)
        layout.addLayout(uniprot_layout)
        
        # Notes
        notes_label = QLabel("Notes:")
        notes_input = QTextEdit()
        notes_input.setMaximumHeight(100)
        notes_input.setStyleSheet(get_input_style())
        layout.addWidget(notes_label)
        layout.addWidget(notes_input)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec() == QDialog.Accepted:
            protein = {
                "name": name_input.text(),
                "mw_kda": mw_input.value(),
                "uniprot_id": uniprot_input.text(),
                "notes": notes_input.toPlainText(),
                "created": datetime.now().isoformat(),
            }
            
            self.custom_proteins.append(protein)
            self._save_custom_proteins()
            
            QMessageBox.information(self, "Success", f"Added {protein['name']} to library")
    
    def _view_custom_proteins(self):
        """View and manage custom proteins"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Custom Protein Library")
        dialog.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        list_widget = QListWidget()
        for protein in self.custom_proteins:
            name = protein.get('name', 'Unknown')
            mw = protein.get('mw_kda', 0.0)
            list_widget.addItem(f"{name} ({mw:.2f} kDa)")
        
        layout.addWidget(list_widget)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        delete_btn = QPushButton("Delete Selected")
        delete_btn.setStyleSheet(get_button_style("error"))
        delete_btn.clicked.connect(lambda: self._delete_custom_protein(list_widget, dialog))
        
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(get_button_style("standard"))
        close_btn.clicked.connect(dialog.accept)
        
        btn_layout.addWidget(delete_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        
        dialog.exec()
    
    def _delete_custom_protein(self, list_widget: QListWidget, dialog: QDialog):
        """Delete selected custom protein"""
        current_row = list_widget.currentRow()
        if current_row < 0:
            return
        
        protein = self.custom_proteins[current_row]
        
        reply = QMessageBox.question(
            dialog,
            "Delete Protein",
            f"Delete {protein['name']}?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            del self.custom_proteins[current_row]
            self._save_custom_proteins()
            list_widget.takeItem(current_row)
    
    def _import_protein_library(self):
        """Import protein library from JSON"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Protein Library",
            str(Path.home()),
            "JSON Files (*.json)"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'r') as f:
                imported = json.load(f)
            
            self.custom_proteins.extend(imported)
            self._save_custom_proteins()
            
            QMessageBox.information(self, "Success", f"Imported {len(imported)} proteins")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to import:\n{str(e)}")
    
    def _export_protein_library(self):
        """Export protein library to JSON"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Protein Library",
            str(Path.home() / "protein_library.json"),
            "JSON Files (*.json)"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'w') as f:
                json.dump(self.custom_proteins, f, indent=2)
            
            QMessageBox.information(self, "Success", "Protein library exported")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export:\n{str(e)}")


# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    app = QApplication(sys.argv)
    
    # Set application font
    font = QFont(Typography.FAMILY, Typography.SIZE_BODY)
    app.setFont(font)
    
    window = SPRExperimentPlanner()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
