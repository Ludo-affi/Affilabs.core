"""Live Right Panel — Acquisition-time info (Active Cycle Card + Queue + Elapsed Time).

Part of Phase 2: Sidebar Redesign for v2.1.
Hidden when not acquiring; shown during acquisition_started → acquisition_stopped.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class LiveRightPanel(QFrame):
    """Right panel for Live page: Active Cycle Card + Queue table + Elapsed time.
    
    Visibility is controlled by acquisition signals (acquisition_started/stopped).
    Widgets are passed by reference (pre-built in sidebar + moved here).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220)
        self.setObjectName("liveRightPanel")
        self.setStyleSheet(
            "QFrame#liveRightPanel { background: #F5F5F7; border-left: 1px solid #D5D5D7; }"
        )
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        # Will be populated by references to existing widgets:
        # - active_cycle_card (from AL_method_builder)
        # - summary_table (QueueSummaryWidget)
        # - elapsed_time_label (new)
        
        self.active_cycle_card = None  # Set by caller
        self.summary_table = None      # Set by caller
        self.elapsed_time_label = QLabel("Elapsed: --:--")
        self.elapsed_time_label.setStyleSheet(
            "QLabel { font-size: 12px; color: #6E6E73; margin-top: 8px; }"
        )
        
        # Placeholder layout; widgets added by caller via add_widget_ref()
        self._container_layout = layout
        
    def add_widget_ref(self, widget, name: str):
        """Add a pre-built widget by reference.
        
        Args:
            widget: Pre-built QWidget (active_cycle_card, summary_table, etc.)
            name: Identifier ('active_cycle_card', 'summary_table', etc.)
        """
        if name == 'active_cycle_card':
            self.active_cycle_card = widget
            self._container_layout.addWidget(widget)
        elif name == 'summary_table':
            self.summary_table = widget
            self._container_layout.addWidget(widget)
    
    def set_elapsed_time(self, elapsed_str: str):
        """Update elapsed time display.
        
        Args:
            elapsed_str: Formatted time string e.g. "04:32"
        """
        self.elapsed_time_label.setText(f"Elapsed: {elapsed_str}")
    
    def reset(self):
        """Reset display for next acquisition."""
        self.set_elapsed_time("--:--")
