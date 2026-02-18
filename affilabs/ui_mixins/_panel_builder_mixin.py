"""Panel builder mixin for AffilabsMainWindow.

Extracted from affilabs/affilabs_core_ui.py to reduce file size.

Methods:
    _create_edits_right_panel   — Right panel with primary graph and thumbnail selectors
    _create_analyze_content     — Analyze tab content layout (left + right panels)
    _create_analyze_left_panel  — Left panel with processed data and statistics graphs
    _create_analyze_right_panel — Right panel with model selection, data table, export
    _create_report_content      — Report tab content layout (left + right panels)
    _create_report_left_panel   — Left panel with report preview canvas
    _create_report_right_panel  — Right panel with report tools and content library
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from affilabs.ui_styles import Colors, Dimensions, Fonts, create_card_shadow


class PanelBuilderMixin:
    """Mixin providing panel-builder methods for AffilabsMainWindow.

    Contains the Edits right-panel, Analyze tab, and Report tab builders
    that were originally in affilabs_core_ui.py.
    """

    def _create_edits_right_panel(self):
        """Create right panel with primary graph and thumbnail selectors."""
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame {  background: {Colors.TRANSPARENT};  }",
        )

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(12)

        # Primary Graph Container
        primary_graph = QFrame()
        primary_graph.setStyleSheet(
            "QFrame {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border-radius: 12px;"
            "}",
        )
        primary_graph.setGraphicsEffect(create_card_shadow())

        primary_layout = QVBoxLayout(primary_graph)
        primary_layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        primary_layout.setSpacing(Dimensions.SPACING_MD)

        # Graph header
        graph_header = QHBoxLayout()
        graph_title = QLabel("Primary Cycle View")
        graph_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        graph_header.addWidget(graph_title)
        graph_header.addStretch()

        # Channel toggles (compact)
        for ch, color in [
            ("A", "#000000"),  # Black
            ("B", "#FF0000"),  # Red
            ("C", "#0000FF"),  # Blue
            ("D", "#00AA00"),  # Green (0, 170, 0)
        ]:
            ch_btn = QPushButton(f"Ch {ch}")
            ch_btn.setCheckable(True)
            ch_btn.setChecked(True)
            ch_btn.setFixedSize(40, 24)
            ch_btn.setStyleSheet(
                f"QPushButton {{"
                f"  background: {color};"
                "  color: white;"
                "  border: none;"
                "  border-radius: 12px;"
                "  font-size: 11px;"
                "  font-weight: 600;"
                "  font-family: {Fonts.SYSTEM};"
                "}"
                "QPushButton:!checked {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  color: {Colors.SECONDARY_TEXT};"
                "}",
            )
            graph_header.addWidget(ch_btn)

        primary_layout.addLayout(graph_header)

        # Create actual PyQtGraph widget for cycle display
        import pyqtgraph as pg
        self.edits_primary_graph = pg.PlotWidget()
        self.edits_primary_graph.setBackground('w')
        self.edits_primary_graph.showGrid(x=True, y=True, alpha=0.3)
        self.edits_primary_graph.setLabel('left', 'Response (RU)')
        self.edits_primary_graph.setLabel('bottom', 'Time (s)')
        self.edits_primary_graph.setMinimumHeight(400)

        # Enable right-click menu for adding flags
        self.edits_primary_graph.scene().sigMouseClicked.connect(self._on_edits_graph_clicked)

        # Install keyboard event filter for flag movement via FlagManager
        # (FlagManager provides unified keyboard handling for both live and edits contexts)
        if hasattr(self, 'app') and hasattr(self.app, 'flag_mgr') and self.app.flag_mgr:
            self.app.flag_mgr.setup_edits_keyboard_filter()

        # Create curves for each channel (matching main window colors)
        self.edits_graph_curves = [
            self.edits_primary_graph.plot(pen=pg.mkPen(color=(0, 0, 0), width=2)),       # Channel A: Black
            self.edits_primary_graph.plot(pen=pg.mkPen(color=(255, 0, 0), width=2)),     # Channel B: Red
            self.edits_primary_graph.plot(pen=pg.mkPen(color=(0, 0, 255), width=2)),     # Channel C: Blue
            self.edits_primary_graph.plot(pen=pg.mkPen(color=(0, 170, 0), width=2)),     # Channel D: Green
        ]

        primary_layout.addWidget(self.edits_primary_graph)

        panel_layout.addWidget(primary_graph, 4)

        # Reference Graphs Container (Phase 3)
        references_container = QFrame()
        references_container.setStyleSheet(
            "QFrame {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border-radius: 12px;"
            "}",
        )
        references_container.setGraphicsEffect(create_card_shadow())

        references_layout = QVBoxLayout(references_container)
        references_layout.setContentsMargins(Dimensions.MARGIN_SM, Dimensions.MARGIN_SM, Dimensions.MARGIN_SM, Dimensions.MARGIN_SM)
        references_layout.setSpacing(Dimensions.SPACING_SM)

        # References label
        ref_header = QHBoxLayout()
        ref_label = QLabel("Reference Graphs")
        ref_label.setStyleSheet(
            "QLabel {"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        ref_header.addWidget(ref_label)

        # Clear all button
        clear_refs_btn = QPushButton("Clear All")
        clear_refs_btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_SM)
        clear_refs_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(0, 0, 0, 0.04);"
            "  color: {Colors.PRIMARY_TEXT};"
            "  border: none;"
            "  border-radius: 14px;"
            "  font-size: 11px;"
            "  font-weight: 500;"
            "  padding: 0px 8px;"
            "  font-family: {Fonts.SYSTEM};"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 0, 0, 0.08);"
            "}",
        )
        clear_refs_btn.clicked.connect(self._clear_reference_graphs)
        ref_header.addWidget(clear_refs_btn)
        references_layout.addLayout(ref_header)

        # Three reference graph widgets
        ref_graphs_layout = QHBoxLayout()
        ref_graphs_layout.setSpacing(8)

        import pyqtgraph as pg
        self.edits_reference_graphs = []
        self.edits_reference_curves = []
        self.edits_reference_cycle_data = [None, None, None]  # Store which cycle is loaded

        for i in range(3):
            # Create container for each reference
            ref_frame = QFrame()
            ref_frame.setStyleSheet(
                "QFrame {"
                "  background: rgba(0, 0, 0, 0.02);"
                "  border-radius: 8px;"
                "}",
            )
            ref_frame.setAcceptDrops(True)

            ref_layout = QVBoxLayout(ref_frame)
            ref_layout.setContentsMargins(4, 4, 4, 4)
            ref_layout.setSpacing(2)

            # Label
            ref_name_label = QLabel("Drag cycle here")
            ref_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ref_name_label.setStyleSheet(
                "QLabel {"
                "  font-size: 10px;"
                "  color: {Colors.SECONDARY_TEXT};"
                "  background: {Colors.TRANSPARENT};"
                "  font-family: {Fonts.SYSTEM};"
                "}",
            )
            ref_layout.addWidget(ref_name_label)

            # Mini graph
            ref_graph = pg.PlotWidget()
            ref_graph.setBackground('w')
            ref_graph.setFixedHeight(120)
            ref_graph.hideAxis('left')
            ref_graph.hideAxis('bottom')
            ref_graph.setMouseEnabled(x=False, y=False)

            # Create curves for 4 channels (matching main window colors)
            ref_curves = [
                ref_graph.plot(pen=pg.mkPen(color=(0, 0, 0), width=1)),       # Channel A: Black
                ref_graph.plot(pen=pg.mkPen(color=(255, 0, 0), width=1)),     # Channel B: Red
                ref_graph.plot(pen=pg.mkPen(color=(0, 0, 255), width=1)),     # Channel C: Blue
                ref_graph.plot(pen=pg.mkPen(color=(0, 170, 0), width=1)),     # Channel D: Green
            ]

            ref_layout.addWidget(ref_graph)

            # Store references
            self.edits_reference_graphs.append(ref_graph)
            self.edits_reference_curves.append(ref_curves)

            # Add to layout
            ref_graphs_layout.addWidget(ref_frame)

            # Store frame and label for later updates
            if not hasattr(self, 'edits_reference_frames'):
                self.edits_reference_frames = []
                self.edits_reference_labels = []
            self.edits_reference_frames.append(ref_frame)
            self.edits_reference_labels.append(ref_name_label)

        references_layout.addLayout(ref_graphs_layout)

        panel_layout.addWidget(references_container, 2)

        return panel

    def _create_analyze_content(self):
        """Create the Analyze tab content with processed data graph, statistics, and kinetic analysis."""
        content_widget = QFrame()
        content_widget.setStyleSheet(
            "QFrame {  background: #F8F9FA;  }",
        )

        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        content_layout.setSpacing(Dimensions.SPACING_MD)

        # Left side: Graphs (Processed Data + Statistics)
        left_panel = self._create_analyze_left_panel()
        content_layout.addWidget(left_panel, 3)

        # Right side: Model Selection + Data Table + Export
        right_panel = self._create_analyze_right_panel()
        content_layout.addWidget(right_panel, 2)

        return content_widget

    def _create_analyze_left_panel(self):
        """Create left panel with processed data and statistics graphs."""
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame {  background: {Colors.TRANSPARENT};  }",
        )

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(12)

        # Main Processed Data Graph
        main_graph = QFrame()
        main_graph.setStyleSheet(
            "QFrame {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border-radius: 12px;"
            "}",
        )
        main_graph.setGraphicsEffect(create_card_shadow())

        main_graph_layout = QVBoxLayout(main_graph)
        main_graph_layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        main_graph_layout.setSpacing(Dimensions.SPACING_MD)

        # Header
        graph_header = QHBoxLayout()
        graph_title = QLabel("Processed Data")
        graph_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        graph_header.addWidget(graph_title)
        graph_header.addStretch()

        # View options
        view_btns = ["Fitted", "Residuals", "Overlay"]
        for i, btn_text in enumerate(view_btns):
            view_btn = QPushButton(btn_text)
            view_btn.setCheckable(True)
            view_btn.setChecked(i == 0)
            view_btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_MD)
            view_btn.setMinimumWidth(72)
            view_btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  color: {Colors.SECONDARY_TEXT};"
                "  border: none;"
                "  border-radius: 14px;"
                "  font-size: 12px;"
                "  font-weight: 500;"
                "  font-family: {Fonts.SYSTEM};"
                "}"
                "QPushButton:checked {"
                "  background: #1D1D1F;"
                "  color: white;"
                "  font-weight: 600;"
                "}"
                "QPushButton:hover:!checked {"
                "  background: rgba(0, 0, 0, 0.1);"
                "}",
            )
            graph_header.addWidget(view_btn)

        main_graph_layout.addLayout(graph_header)

        # Graph canvas
        graph_canvas = QFrame()
        graph_canvas.setStyleSheet(
            "QFrame {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border-radius: 8px;"
            "}",
        )
        canvas_layout = QVBoxLayout(graph_canvas)
        canvas_placeholder = QLabel(
            "[Processed Data Graph]\n\n"
            "Fitted curves with model overlay\n"
            "Interactive zoom and pan enabled",
        )
        canvas_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        canvas_placeholder.setStyleSheet(
            "QLabel {"
            "  font-size: 12px;"
            "  color: #C7C7CC;"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        canvas_layout.addWidget(canvas_placeholder)
        main_graph_layout.addWidget(graph_canvas, 1)

        panel_layout.addWidget(main_graph, 3)

        # Statistics / Goodness of Fit Graph
        stats_graph = QFrame()
        stats_graph.setStyleSheet(
            "QFrame {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border-radius: 12px;"
            "}",
        )
        stats_graph.setGraphicsEffect(create_card_shadow())

        stats_layout = QVBoxLayout(stats_graph)
        stats_layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        stats_layout.setSpacing(Dimensions.SPACING_MD)

        # Header
        stats_header = QHBoxLayout()
        stats_title = QLabel("Goodness of Fit Analysis")
        stats_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        stats_header.addWidget(stats_title)
        stats_header.addStretch()

        # R² display
        r_squared = QLabel("R² = 0.9987")
        r_squared.setStyleSheet(
            "QLabel {"
            "  background: rgba(52, 199, 89, 0.1);"
            "  color: #34C759;"
            "  border-radius: 8px;"
            "  padding: 6px 12px;"
            "  font-size: 12px;"
            "  font-weight: 600;"
            f"  font-family: {Fonts.MONOSPACE};"
            "}",
        )
        stats_header.addWidget(r_squared)

        stats_layout.addLayout(stats_header)

        # Stats canvas
        stats_canvas = QFrame()
        stats_canvas.setStyleSheet(
            "QFrame {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border-radius: 8px;"
            "}",
        )
        stats_canvas_layout = QVBoxLayout(stats_canvas)
        stats_placeholder = QLabel(
            "[Residuals / Chi-Square Plot]\n\n"
            "Statistical analysis visualization\n"
            "Chi² = 1.23e-4, RMSE = 0.012",
        )
        stats_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stats_placeholder.setStyleSheet(
            "QLabel {"
            "  font-size: 12px;"
            "  color: #C7C7CC;"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        stats_canvas_layout.addWidget(stats_placeholder)
        stats_layout.addWidget(stats_canvas, 1)

        panel_layout.addWidget(stats_graph, 2)

        return panel

    def _create_analyze_right_panel(self):
        """Create right panel with model selection, data table, and export options."""
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame {  background: {Colors.TRANSPARENT};  }",
        )

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(12)

        # Mathematical Model Selection
        model_container = QFrame()
        model_container.setStyleSheet(
            "QFrame {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border-radius: 12px;"
            "}",
        )
        model_container.setGraphicsEffect(create_card_shadow())

        model_layout = QVBoxLayout(model_container)
        model_layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        model_layout.setSpacing(Dimensions.SPACING_MD)

        # Header
        model_title = QLabel("Mathematical Model")
        model_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        model_layout.addWidget(model_title)

        # Model selection dropdown
        from PySide6.QtWidgets import QComboBox

        model_dropdown = QComboBox()
        model_dropdown.addItems(
            [
                "Langmuir 1:1",
                "Two-State Binding",
                "Bivalent Analyte",
                "Mass Transport Limited",
                "Heterogeneous Ligand",
                "Custom Model",
            ],
        )
        model_dropdown.setFixedHeight(Dimensions.HEIGHT_BUTTON_LG)
        model_dropdown.setStyleSheet(
            "QComboBox {"
            "  background: rgba(0, 0, 0, 0.04);"
            "  color: {Colors.PRIMARY_TEXT};"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 8px;"
            "  padding: 8px 12px;"
            "  font-size: 13px;"
            "  font-weight: 500;"
            "  font-family: {Fonts.SYSTEM};"
            "}"
            "QComboBox:hover {"
            "  background: rgba(0, 0, 0, 0.08);"
            "}"
            "QComboBox::drop-down {"
            "  border: none;"
            "  width: 20px;"
            "}"
            "QComboBox::down-arrow {"
            "  image: none;"
            "}",
        )
        model_layout.addWidget(model_dropdown)

        # Fit button
        fit_btn = QPushButton("Run Fitting Analysis")
        fit_btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_LG)
        fit_btn.setStyleSheet(
            "QPushButton {"
            "  background: #1D1D1F;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 14px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  font-family: {Fonts.SYSTEM};"
            "}"
            "QPushButton:hover {"
            "  background: #3A3A3C;"
            "}"
            "QPushButton:pressed {"
            "  background: #48484A;"
            "}",
        )
        model_layout.addWidget(fit_btn)

        # Model parameters info
        params_label = QLabel("Model Parameters")
        params_label.setStyleSheet(
            "QLabel {"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  margin-top: 8px;"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        model_layout.addWidget(params_label)

        params_info = QLabel(
            "ka: Association rate constant\n"
            "kd: Dissociation rate constant\n"
            "KD: Equilibrium constant\n"
            "Rmax: Maximum response",
        )
        params_info.setStyleSheet(
            "QLabel {"
            "  font-size: 11px;"
            "  color: {Colors.SECONDARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  line-height: 1.6;"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        model_layout.addWidget(params_info)

        panel_layout.addWidget(model_container)

        # Kinetic Data Table
        data_container = QFrame()
        data_container.setStyleSheet(
            "QFrame {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border-radius: 12px;"
            "}",
        )
        data_container.setGraphicsEffect(create_card_shadow())

        data_layout = QVBoxLayout(data_container)
        data_layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        data_layout.setSpacing(Dimensions.SPACING_MD)

        # Header
        data_header = QHBoxLayout()
        data_title = QLabel("Kinetic Results")
        data_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        data_header.addWidget(data_title)
        data_header.addStretch()

        copy_btn = QPushButton("?? Copy")
        copy_btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_MD)
        copy_btn.setMinimumWidth(72)
        copy_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(0, 0, 0, 0.06);"
            "  color: {Colors.PRIMARY_TEXT};"
            "  border: none;"
            "  border-radius: 14px;"
            "  font-size: 12px;"
            "  font-weight: 500;"
            "  font-family: {Fonts.SYSTEM};"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 0, 0, 0.1);"
            "}",
        )
        data_header.addWidget(copy_btn)

        data_layout.addLayout(data_header)

        # Data table
        from PySide6.QtWidgets import QHeaderView, QTableWidget

        data_table = QTableWidget(4, 2)
        data_table.setHorizontalHeaderLabels(["Parameter", "Value"])
        data_table.horizontalHeader().setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )
        data_table.horizontalHeader().setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )
        data_table.setStyleSheet(
            "QTableWidget {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border: none;"
            "  border-radius: 8px;"
            "  gridline-color: rgba(0, 0, 0, 0.06);"
            "  font-size: 12px;"
            "  font-family: {Fonts.SYSTEM};"
            "}"
            "QTableWidget::item {"
            "  padding: 8px;"
            "  color: {Colors.PRIMARY_TEXT};"
            "}"
            "QHeaderView::section {"
            "  background: rgba(0, 0, 0, 0.03);"
            "  color: {Colors.SECONDARY_TEXT};"
            "  padding: 8px;"
            "  border: none;"
            "  border-bottom: 1px solid rgba(0, 0, 0, 0.08);"
            "  font-weight: 600;"
            "  font-size: 11px;"
            "}",
        )

        # Sample data
        from PySide6.QtWidgets import QTableWidgetItem

        results = [
            ("ka (M⁻¹s⁻¹)", "1.23e5 ± 0.04e5"),
            ("kd (s⁻¹)", "3.45e-4 ± 0.12e-4"),
            ("KD (M)", "2.80e-9 ± 0.15e-9"),
            ("? SPR (nm)", "0.45 ± 0.02"),
        ]

        for row, (param, value) in enumerate(results):
            data_table.setItem(row, 0, QTableWidgetItem(param))
            data_table.setItem(row, 1, QTableWidgetItem(value))

        data_layout.addWidget(data_table, 1)

        panel_layout.addWidget(data_container, 1)

        # Export/Save Section
        export_container = QFrame()
        export_container.setStyleSheet(
            "QFrame {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border-radius: 12px;"
            "}",
        )
        export_container.setGraphicsEffect(create_card_shadow())

        export_layout = QVBoxLayout(export_container)
        export_layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        export_layout.setSpacing(Dimensions.SPACING_MD)

        export_title = QLabel("Export Data")
        export_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        export_layout.addWidget(export_title)

        # Export buttons
        export_btns = QHBoxLayout()
        export_btns.setSpacing(8)

        csv_btn = QPushButton("Save CSV")
        csv_btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_LG)
        csv_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(0, 0, 0, 0.04);"
            "  color: {Colors.PRIMARY_TEXT};"
            "  border: none;"
            "  border-radius: 14px;"
            "  font-size: 13px;"
            "  font-weight: 500;"
            "  font-family: {Fonts.SYSTEM};"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 0, 0, 0.08);"
            "}",
        )
        export_btns.addWidget(csv_btn)

        json_btn = QPushButton("Save JSON")
        json_btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_LG)
        json_btn.setStyleSheet(csv_btn.styleSheet())
        export_btns.addWidget(json_btn)

        export_layout.addLayout(export_btns)

        # Export graph image button (full width)
        image_btn = QPushButton("?? Export Active Cycle Image")
        image_btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_LG)
        image_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(0, 122, 255, 0.1);"
            "  color: #007AFF;"
            "  border: none;"
            "  border-radius: 14px;"
            "  font-size: 13px;"
            "  font-weight: 500;"
            "  font-family: {Fonts.SYSTEM};"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 122, 255, 0.2);"
            "}",
        )
        image_btn.setToolTip("Export the active cycle graph as a high-resolution PNG image")
        self.export_image_btn = image_btn
        export_layout.addWidget(image_btn)

        export_layout.addLayout(export_btns)

        panel_layout.addWidget(export_container)

        panel_layout.addStretch()

        return panel

    def _create_report_content(self):
        """Create the Report tab content for generating PDF reports with graphs, tables, and notes."""
        content_widget = QFrame()
        content_widget.setStyleSheet(
            "QFrame {  background: #F8F9FA;  }",
        )

        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        content_layout.setSpacing(Dimensions.SPACING_MD)

        # Left side: Report Canvas/Preview
        left_panel = self._create_report_left_panel()
        content_layout.addWidget(left_panel, 3)

        # Right side: Tools and Content Library
        right_panel = self._create_report_right_panel()
        content_layout.addWidget(right_panel, 2)

        return content_widget

    def _create_report_left_panel(self):
        """Create left panel with report preview canvas."""
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame {  background: {Colors.TRANSPARENT};  }",
        )

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(12)

        # Report header with export
        header = QHBoxLayout()

        report_title = QLabel("Report Preview")
        report_title.setStyleSheet(
            "QLabel {"
            "  font-size: 17px;"
            "  font-weight: 600;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
            "}",
        )
        header.addWidget(report_title)
        header.addStretch()

        # Generate PDF button
        pdf_btn = QPushButton("?? Generate PDF")
        pdf_btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_XL)
        pdf_btn.setMinimumWidth(140)
        pdf_btn.setStyleSheet(
            "QPushButton {"
            "  background: #FF3B30;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 14px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  padding: 0px 20px;"
            "  font-family: {Fonts.SYSTEM};"
            "}"
            "QPushButton:hover {"
            "  background: #E6342A;"
            "}"
            "QPushButton:pressed {"
            "  background: #CC2E25;"
            "}",
        )
        header.addWidget(pdf_btn)

        panel_layout.addLayout(header)

        # Report canvas/preview area
        canvas = QFrame()
        canvas.setStyleSheet(
            "QFrame {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border-radius: 12px;"
            "}",
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(0, 0, 0, 25))
        shadow.setOffset(0, 4)
        canvas.setGraphicsEffect(shadow)

        canvas_layout = QVBoxLayout(canvas)
        canvas_layout.setContentsMargins(24, 24, 24, 24)
        canvas_layout.setSpacing(16)

        # Report content area with scroll
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(
            "QScrollArea {    background: {Colors.TRANSPARENT};}",
        )

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        scroll_layout.setSpacing(20)

        # Sample report elements
        # Title
        title_edit = QLabel("Kinetic Analysis Report")
        title_edit.setStyleSheet(
            "QLabel {"
            "  font-size: 24px;"
            "  font-weight: {Fonts.WEIGHT_BOLD};"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  padding: 8px;"
            "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
            "}",
        )
        scroll_layout.addWidget(title_edit)

        # Date/Info
        info_label = QLabel("Date: November 20, 2025\nExperiment ID: EXP-2025-001")
        info_label.setStyleSheet(
            "QLabel {"
            "  font-size: 12px;"
            "  color: {Colors.SECONDARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  padding: 4px 8px;"
            "  line-height: 1.6;"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        scroll_layout.addWidget(info_label)

        # Placeholder for graph
        graph_placeholder = QFrame()
        graph_placeholder.setFixedHeight(250)
        graph_placeholder.setStyleSheet(
            "QFrame {"
            "  background: rgba(0, 122, 255, 0.05);"
            "  border-radius: 8px;"
            "}",
        )
        graph_label = QLabel("[Graph Element]\n\nClick to insert graph")
        graph_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        graph_label.setStyleSheet(
            "QLabel {"
            "  font-size: 13px;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        graph_layout = QVBoxLayout(graph_placeholder)
        graph_layout.addWidget(graph_label)
        scroll_layout.addWidget(graph_placeholder)

        # Notes section
        notes_label = QLabel("Notes:")
        notes_label.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  padding: 8px;"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        scroll_layout.addWidget(notes_label)

        notes_edit = QTextEdit()
        notes_edit.setPlaceholderText(
            "Add experiment notes, observations, or conclusions...",
        )
        notes_edit.setFixedHeight(120)
        notes_edit.setStyleSheet(
            "QTextEdit {"
            "  background: rgba(0, 0, 0, 0.03);"
            "  border: none;"
            "  border-radius: 8px;"
            "  padding: 12px;"
            "  font-size: 13px;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        scroll_layout.addWidget(notes_edit)

        # Table placeholder
        table_placeholder = QFrame()
        table_placeholder.setFixedHeight(180)
        table_placeholder.setStyleSheet(
            "QFrame {"
            "  background: rgba(52, 199, 89, 0.05);"
            "  border-radius: 8px;"
            "}",
        )
        table_label = QLabel("[Table Element]\n\nClick to insert data table")
        table_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        table_label.setStyleSheet(
            "QLabel {"
            "  font-size: 13px;"
            "  color: #34C759;"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        table_layout = QVBoxLayout(table_placeholder)
        table_layout.addWidget(table_label)
        scroll_layout.addWidget(table_placeholder)

        scroll_layout.addStretch()

        scroll_area.setWidget(scroll_content)
        canvas_layout.addWidget(scroll_area, 1)

        panel_layout.addWidget(canvas, 1)

        return panel

    def _create_report_right_panel(self):
        """Create right panel with report tools and content library."""
        panel = QFrame()
        panel.setStyleSheet(
            "QFrame {  background: {Colors.TRANSPARENT};  }",
        )

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(12)

        # Insert Elements Section
        elements_container = QFrame()
        elements_container.setStyleSheet(
            "QFrame {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border-radius: 12px;"
            "}",
        )
        elements_container.setGraphicsEffect(create_card_shadow())

        elements_layout = QVBoxLayout(elements_container)
        elements_layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        elements_layout.setSpacing(Dimensions.SPACING_MD)

        elements_title = QLabel("Insert Elements")
        elements_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        elements_layout.addWidget(elements_title)

        # Element buttons
        element_btns = [
            ("📊 Graph", "Insert saved graph"),
            ("📈 Bar Chart", "Create bar chart"),
            ("📋 Table", "Insert data table"),
            ("📝 Text Box", "Add text section"),
            ("🖼️ Image", "Insert image"),
        ]

        for icon_text, tooltip in element_btns:
            elem_btn = QPushButton(icon_text)
            elem_btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_LG)
            elem_btn.setToolTip(tooltip)
            elem_btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.04);"
                "  color: {Colors.PRIMARY_TEXT};"
                "  border: none;"
                "  border-radius: 14px;"
                "  font-size: 13px;"
                "  font-weight: 500;"
                "  text-align: left;"
                "  padding-left: 12px;"
                "  font-family: {Fonts.SYSTEM};"
                "}"
                "QPushButton:hover {"
                "  background: rgba(0, 0, 0, 0.08);"
                "}"
                "QPushButton:pressed {"
                "  background: rgba(0, 0, 0, 0.12);"
                "}",
            )
            elements_layout.addWidget(elem_btn)

        panel_layout.addWidget(elements_container)

        # Chart Builder Tool
        chart_container = QFrame()
        chart_container.setStyleSheet(
            "QFrame {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border-radius: 12px;"
            "}",
        )
        chart_container.setGraphicsEffect(create_card_shadow())

        chart_layout = QVBoxLayout(chart_container)
        chart_layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        chart_layout.setSpacing(Dimensions.SPACING_MD)

        chart_title = QLabel("Chart Builder")
        chart_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        chart_layout.addWidget(chart_title)

        # Chart type selector
        chart_types = QHBoxLayout()
        chart_types.setSpacing(6)

        for chart_type in ["Bar", "Line", "Scatter"]:
            type_btn = QPushButton(chart_type)
            type_btn.setCheckable(True)
            type_btn.setChecked(chart_type == "Bar")
            type_btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_STD)
            type_btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.06);"
                "  color: {Colors.SECONDARY_TEXT};"
                "  border: none;"
                "  border-radius: 14px;"
                "  font-size: 12px;"
                "  font-weight: 500;"
                "  font-family: {Fonts.SYSTEM};"
                "}"
                "QPushButton:checked {"
                "  background: #1D1D1F;"
                "  color: white;"
                "  font-weight: 600;"
                "}",
            )
            chart_types.addWidget(type_btn)

        chart_layout.addLayout(chart_types)

        # Data source
        source_label = QLabel("Data Source:")
        source_label.setStyleSheet(
            "QLabel {"
            "  font-size: 12px;"
            "  color: {Colors.SECONDARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        chart_layout.addWidget(source_label)

        from PySide6.QtWidgets import QComboBox

        source_dropdown = QComboBox()
        source_dropdown.addItems(
            [
                "Kinetic Results",
                "Cycle Statistics",
                "Custom Data",
            ],
        )
        source_dropdown.setFixedHeight(Dimensions.HEIGHT_BUTTON_STD)
        source_dropdown.setStyleSheet(
            "QComboBox {"
            "  background: rgba(0, 0, 0, 0.04);"
            "  color: {Colors.PRIMARY_TEXT};"
            "  border: 1px solid rgba(0, 0, 0, 0.1);"
            "  border-radius: 8px;"
            "  padding: 6px 10px;"
            "  font-size: 12px;"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        chart_layout.addWidget(source_dropdown)

        # Create chart button
        create_chart_btn = QPushButton("Create Chart")
        create_chart_btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_LG)
        create_chart_btn.setStyleSheet(
            "QPushButton {"
            "  background: #1D1D1F;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 14px;"
            "  font-size: 13px;"
            "  font-weight: 600;"
            "  font-family: {Fonts.SYSTEM};"
            "}"
            "QPushButton:hover {"
            "  background: #3A3A3C;"
            "}",
        )
        chart_layout.addWidget(create_chart_btn)

        panel_layout.addWidget(chart_container)

        # Saved Content Library
        library_container = QFrame()
        library_container.setStyleSheet(
            "QFrame {"
            "  background: {Colors.BACKGROUND_WHITE};"
            "  border-radius: 12px;"
            "}",
        )
        library_container.setGraphicsEffect(create_card_shadow())

        library_layout = QVBoxLayout(library_container)
        library_layout.setContentsMargins(Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD, Dimensions.MARGIN_MD)
        library_layout.setSpacing(Dimensions.SPACING_MD)

        library_title = QLabel("Content Library")
        library_title.setStyleSheet(
            "QLabel {"
            "  font-size: 15px;"
            "  font-weight: 600;"
            "  color: {Colors.PRIMARY_TEXT};"
            "  background: {Colors.TRANSPARENT};"
            "  font-family: {Fonts.SYSTEM};"
            "}",
        )
        library_layout.addWidget(library_title)

        # Saved items list
        saved_items = [
            "📊 Sensorgram_ChA",
            "📈 Kinetic_Fit_Plot",
            "📋 Results_Table_1",
        ]

        for item in saved_items:
            item_btn = QPushButton(item)
            item_btn.setFixedHeight(Dimensions.HEIGHT_BUTTON_STD)
            item_btn.setStyleSheet(
                "QPushButton {"
                "  background: rgba(0, 0, 0, 0.03);"
                "  color: {Colors.PRIMARY_TEXT};"
                "  border: none;"
                "  border-radius: 14px;"
                "  font-size: 12px;"
                "  font-weight: 400;"
                "  text-align: left;"
                "  padding-left: 12px;"
                "  font-family: {Fonts.SYSTEM};"
                "}"
                "QPushButton:hover {"
                "  background: rgba(0, 0, 0, 0.06);"
                "}",
            )
            library_layout.addWidget(item_btn)

        panel_layout.addWidget(library_container, 1)

        panel_layout.addStretch()

        return panel
