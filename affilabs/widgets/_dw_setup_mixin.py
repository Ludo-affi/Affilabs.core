"""Setup mixin for DataWindow.

Extracted from affilabs/widgets/datawindow.py to reduce file size.

Methods:
    update_table_style           — Update the style of the cycle table
    _fix_checkbox_styles         — Fix checkbox and label styling to use global theme
    toggle_table_style           — Toggle the style of the table
    resizeEvent                  — Resize the widget; splitter handles graph resizing
    _position_bg_rect            — Position background rectangle to match graph area
    _position_channel_overlay    — Keep channel display block aligned with sensorgram edge
    eventFilter                  — Handle double-click on splitter handle to swap ratios
    _swap_graph_ratios           — Swap graph size ratios: 30/70 ↔ 70/30
    take_sensorgram_controls_panel — Detach right-hand sensorgram controls for sidebar
    setup                        — Set up the widget with master-detail layout
    _clear_layout                — Recursively remove widgets/layouts while keeping alive
    _update_display_group_width  — Clamp display checkbox group to at most half graph width
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing_extensions import Self
else:
    try:
        from typing import Self
    except ImportError:
        from typing_extensions import Self

from PySide6.QtCore import QPoint, Qt, QTimer, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLayout,
    QSizePolicy,
    QSplitter,
)

from affilabs.ui.ui_processing import Ui_Processing
from affilabs.ui.ui_sensorgram import Ui_Sensorgram
from affilabs.utils.logger import logger
from affilabs.widgets.graphs import SegmentGraph, SensorgramGraph


class SetupMixin:
    """Mixin providing layout-setup and event-filter methods for DataWindow.

    Contains update_table_style, _fix_checkbox_styles, toggle_table_style,
    resizeEvent, _position_bg_rect, _position_channel_overlay, eventFilter,
    _swap_graph_ratios, take_sensorgram_controls_panel, setup, _clear_layout,
    and _update_display_group_width, originally in affilabs/widgets/datawindow.py.
    """

    def update_table_style(self: Self) -> None:
        """Update the style of the cycle table."""
        self._get_table_manager().update_table_style()

    def _fix_checkbox_styles(self: Self) -> None:
        """Fix checkbox and label styling to use global theme.

        The UI files have inline styles that override the global theme,
        causing gray shades and invisible checkmarks. This method clears
        those problematic inline styles while preserving text colors.
        """
        # Fix channel checkboxes - clear background but keep text color
        for checkbox_name in ["segment_A", "segment_B", "segment_C", "segment_D"]:
            if hasattr(self.ui, checkbox_name):
                checkbox = getattr(self.ui, checkbox_name)
                # Get current text color from stylesheet
                current_style = checkbox.styleSheet()
                if "color:" in current_style:
                    # Extract just the color line
                    import re

                    color_match = re.search(r"color:\s*([^;]+);", current_style)
                    if color_match:
                        color_value = color_match.group(1).strip()
                        # Set only text color, let global theme handle the rest
                        checkbox.setStyleSheet(
                            f"QCheckBox {{ color: {color_value}; background-color: transparent; }}",
                        )
                else:
                    checkbox.setStyleSheet(
                        "QCheckBox { background-color: transparent; }",
                    )

    @Slot()
    def toggle_table_style(self: Self) -> None:
        """Toggle the style of the table."""
        self._get_table_manager().toggle_table_style()

    def resizeEvent(self: Self, _: object) -> None:  # noqa: N802
        """Resize the widget - splitter handles graph resizing automatically."""
        super().resizeEvent(_)

        # Reposition background rectangle when window resizes
        self._position_bg_rect()
        self._position_channel_overlay()

    def _position_bg_rect(self: Self) -> None:
        """Position and size the background rectangle to match graph area with margins."""
        if hasattr(self, "bg_rect_widget") and hasattr(self, "graph_splitter"):
            # Get splitter's geometry in DataWindow's coordinate space
            splitter_pos = self.graph_splitter.pos()
            splitter_width = self.graph_splitter.width()
            splitter_height = self.graph_splitter.height()

            # Calculate rectangle geometry based on splitter size minus margins
            rect_x = splitter_pos.x() + self.bg_rect_margin_left
            rect_y = splitter_pos.y() + self.bg_rect_margin_top
            rect_width = (
                splitter_width - self.bg_rect_margin_left - self.bg_rect_margin_right
            )
            rect_height = (
                splitter_height - self.bg_rect_margin_top - self.bg_rect_margin_bottom
            )

            # Set geometry (position and size) in DataWindow coordinate space
            self.bg_rect_widget.setGeometry(rect_x, rect_y, rect_width, rect_height)

            # Show and ensure it's behind the splitter
            if not self.bg_rect_widget.isVisible():
                self.bg_rect_widget.lower()
                self.bg_rect_widget.show()
                self.graph_splitter.raise_()

    def _position_channel_overlay(self: Self) -> None:
        """Keep the channel display block aligned with the sensorgram graph edge."""
        if not hasattr(self, "channel_overlay"):
            return

        if not hasattr(self, "sensorgram_frame") or not hasattr(
            self,
            "full_segment_view",
        ):
            return

        # Map graph's origin into the sensorgram frame so we can align precisely
        top_left = self.full_segment_view.mapTo(self.sensorgram_frame, QPoint(0, 0))
        x_offset = getattr(self, "_channel_overlay_left_offset", 0)
        y_offset = getattr(self, "_channel_overlay_top_offset", 0)
        self.channel_overlay.move(top_left.x() + x_offset, top_left.y() + y_offset)
        self.channel_overlay.raise_()

    def eventFilter(self, obj, event):
        """Handle double-click on splitter handle to swap graph ratios and splitter resize."""
        import time

        from PySide6.QtCore import QEvent

        # Check if double-click on splitter or its handle
        if hasattr(self, "graph_splitter"):
            is_splitter = obj == self.graph_splitter
            is_handle = obj == self.graph_splitter.handle(1)

            if is_splitter or is_handle:
                event_type = event.type()

                # Reposition background rectangle when splitter resizes
                if event_type == QEvent.Type.Resize and is_splitter:
                    self._position_bg_rect()

                # Manual double-click detection using time tracking
                if event_type == QEvent.Type.MouseButtonPress:
                    current_time = time.time()

                    # Initialize last_click_time if it doesn't exist
                    if not hasattr(self, "_last_click_time"):
                        self._last_click_time = 0

                    # Check if this is a double-click (< 500ms between clicks)
                    time_diff = current_time - self._last_click_time
                    if time_diff < 0.5:
                        logger.info("Double-click detected - swapping graph ratios")
                        self._swap_graph_ratios()
                        self._last_click_time = 0  # Reset to prevent triple-click
                        return True
                    self._last_click_time = current_time

        return super().eventFilter(obj, event)

    def _swap_graph_ratios(self):
        """Swap graph size ratios: 30/70 ↔ 70/30."""
        if not hasattr(self, "graph_splitter"):
            return

        self._detail_focused = not self._detail_focused

        if self._detail_focused:
            # Detail view gets 70% (default)
            self.graph_splitter.setStretchFactor(0, 3)  # Overview: 30%
            self.graph_splitter.setStretchFactor(1, 7)  # Detail: 70%
            logger.debug("Graph ratio: Overview 30% / Detail 70%")
        else:
            # Overview gets 70% (reversed)
            self.graph_splitter.setStretchFactor(0, 7)  # Overview: 70%
            self.graph_splitter.setStretchFactor(1, 3)  # Detail: 30%
            logger.debug("Graph ratio: Overview 70% / Detail 30%")

        # Force splitter to update sizes
        total_height = self.graph_splitter.height()
        if self._detail_focused:
            sizes = [int(total_height * 0.3), int(total_height * 0.7)]
        else:
            sizes = [int(total_height * 0.7), int(total_height * 0.3)]
        self.graph_splitter.setSizes(sizes)

    def take_sensorgram_controls_panel(self) -> QWidget | None:
        """Detach the right-hand sensorgram controls so they can live in the sidebar."""
        if not isinstance(self.ui, Ui_Sensorgram):
            return None

        container = getattr(self.ui, "controls_container", None)
        if container is None:
            return None

        if not self._controls_detached:
            parent_layout = getattr(self.ui, "horizontalLayout", None)
            if isinstance(parent_layout, QHBoxLayout):
                parent_layout.removeWidget(container)
            container.setParent(None)
            self._controls_detached = True

        return container

    def setup(self: Self) -> None:
        """Set up the widget with master-detail layout (30% overview / 70% detail)."""
        title = (
            "Full Experiment Timeline"
            if self.data_source == "dynamic"
            else "Data Processing"
        )

        # Create modern graph containers with Rev 1 styling
        from affilabs.widgets.graph_components import GraphContainer

        # Top graph (Overview) - 30%
        self.sensorgram_frame = GraphContainer(title, height=200, show_delta_spr=False)
        self.sensorgram_frame.setMinimumHeight(150)
        self.sensorgram_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        # Create graph and embed it
        self.full_segment_view = SensorgramGraph(title, show_title=False)
        self.full_segment_view.setMinimumHeight(150)
        self.full_segment_view.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.sensorgram_frame.set_graph_widget(self.full_segment_view)

        # Bottom graph (Cycle of Interest) - 70%
        self.soi_frame = GraphContainer(
            "Cycle of Interest",
            height=400,
            show_delta_spr=True,
        )
        self.soi_frame.setMinimumHeight(200)
        self.soi_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        # Create graph and embed it
        self.SOI_view = SegmentGraph("Cycle of Interest", self.unit, show_title=False)
        self.SOI_view.setMinimumHeight(200)
        self.SOI_view.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.soi_frame.set_graph_widget(self.SOI_view)

        # Create vertical splitter for master-detail layout with modern grayscale styling
        self.graph_splitter = QSplitter(Qt.Orientation.Vertical)
        self.graph_splitter.addWidget(self.sensorgram_frame)
        self.graph_splitter.addWidget(self.soi_frame)

        # Style the splitter handle with grayscale theme
        self.graph_splitter.setStyleSheet("""
            QSplitter {
                background-color: transparent;
                spacing: 8px;
            }
            QSplitter::handle {
                background: rgba(0, 0, 0, 0.1);
                border: none;
                border-radius: 4px;
                margin: 0px 16px;
                height: 8px;
            }
            QSplitter::handle:hover {
                background: rgba(0, 0, 0, 0.15);
            }
            QSplitter::handle:pressed {
                background: #1D1D1F;
            }
        """)

        # Track layout mode for ratio swapping
        self._detail_focused = (
            True  # True = 30/70 (detail gets 70%), False = 70/30 (overview gets 70%)
        )

        # Set proportions: 3 parts overview, 7 parts detail (30%/70%)
        self.graph_splitter.setStretchFactor(0, 3)
        self.graph_splitter.setStretchFactor(1, 7)

        # Set handle width for visible appearance
        self.graph_splitter.setHandleWidth(8)

        # Make splitter more responsive
        self.graph_splitter.setChildrenCollapsible(
            False,
        )  # Prevent graphs from collapsing completely

        # Configure the splitter handle to capture events
        handle = self.graph_splitter.handle(1)
        handle.setEnabled(True)
        handle.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        handle.setToolTip(
            "Drag to resize graphs\nDouble-click to swap sizes (20/80 ↔ 80/20)",
        )

        # Install event filter on BOTH handle and splitter to catch double-click
        # (splitter handles consume events, so we need both levels)
        handle.installEventFilter(self)
        self.graph_splitter.installEventFilter(self)

        # Install resize event filter for splitter to reposition background rectangle
        self.graph_splitter.installEventFilter(self)

        logger.debug("Event filter installed on splitter and handle")

        # Add splitter to UI - handle both UI types (Sensorgram and Processing)
        if hasattr(self.ui, "displays"):
            # Ui_Sensorgram uses 'displays' layout
            target_layout = self.ui.displays
        elif hasattr(self.ui, "verticalLayout_5"):
            # Ui_Processing uses 'verticalLayout_5'
            target_layout = self.ui.verticalLayout_5
        else:
            logger.error("Cannot find target layout for graphs")
            return

        # Only clear layout if it has old widgets (optimization)
        if target_layout.count() > 0:
            self._clear_layout(target_layout)

        # Remove extra padding so graphs can use the full width/height
        target_layout.setContentsMargins(0, 0, 0, 0)
        target_layout.setSpacing(6)

        # Rebuild the top-of-graph controls for the Sensorgram UI
        is_sensorgram = isinstance(self.ui, Ui_Sensorgram)
        # shift_display_box removed from UI

        if is_sensorgram and hasattr(self.ui, "groupBox"):
            # Hide the groupBox since we now have legend checkboxes in Cycle of Interest
            self.ui.groupBox.setVisible(False)

            # Hide the standalone Clear Graph button since it's in the groupBox
            if hasattr(self.ui, "clear_graph_btn"):
                self.ui.clear_graph_btn.hide()

            if hasattr(self.ui, "groupBox_display_right"):
                self.ui.groupBox_display_right.setVisible(False)

        target_layout.addWidget(self.graph_splitter)

        # Position background rectangle after splitter is in layout
        if hasattr(self, "bg_rect_widget"):
            # Keep as child of DataWindow, position will be calculated relative to splitter
            QTimer.singleShot(0, self._position_bg_rect)
        self._update_display_group_width()

    def _clear_layout(self: Self, layout: QLayout) -> None:
        """Recursively remove widgets/layouts while keeping objects alive."""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.setParent(None)
            elif child_layout is not None:
                self._clear_layout(child_layout)

    def _update_display_group_width(self: Self) -> None:
        """Clamp the display checkbox group to at most half the graph width."""
        if not isinstance(self.ui, Ui_Sensorgram):
            return
        if not hasattr(self, "graph_splitter"):
            return
        max_width = max(250, int(self.graph_splitter.width() * 0.5))
        self.ui.groupBox.setMaximumWidth(max_width)
