"""Inject mixin for DataWindow.

Extracted from affilabs/widgets/datawindow.py to reduce file size.

Methods:
    set_inject_callback — Set callback for Inject button
    _on_inject_clicked  — Handle UI Inject button click by delegating to provided callback
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing_extensions import Self
else:
    try:
        from typing import Self
    except ImportError:
        from typing_extensions import Self

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QBrush, QColor, QDoubleValidator, QFont, QPen
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QPushButton,
    QScrollArea,
)

from affilabs.ui.ui_processing import Ui_Processing
from affilabs.ui.ui_sensorgram import Ui_Sensorgram
from affilabs.utils.logger import logger
from affilabs.widgets.channelmenu import ChannelMenu
from affilabs.widgets.cycle_manager import CycleManager
from affilabs.widgets.cycle_table_dialog import CycleTableDialog
from affilabs.widgets.delegates import CycleTypeDelegate, TextInputDelegate
from affilabs.widgets.message import show_message
from affilabs.widgets.metadata import Metadata
from affilabs.widgets.table_manager import CycleTableManager
from settings import CH_LIST

from affilabs.widgets._dw_models import LOOP_BRUSH, SENSOR_BRUSH, PROGRESS_BAR_UPDATE_TIME


class InjectMixin:
    """Mixin providing inject-button methods for DataWindow.

    Contains set_inject_callback and _on_inject_clicked, originally in
    affilabs/widgets/datawindow.py.
    """

    def set_inject_callback(self: Self, callback) -> None:
        """Set callback for Inject button.

        The callback should perform the injection sequence using the
        application's pump control path (e.g., a PumpManager or controller).
        """
        self._inject_callback = callback

    @Slot()
    def _on_inject_clicked(self: Self) -> None:
        """Handle UI Inject button click by delegating to provided callback."""
        if getattr(self, "busy", False):
            show_message("System busy — cannot start injection right now.")
            return
        if callable(getattr(self, "_inject_callback", None)):
            try:
                self._inject_callback()
            except Exception as e:
                logger.error(f"Injection callback error: {e}")
                show_message("Injection failed to start. See logs.")
        else:
            logger.warning("No injection callback set; ignoring Inject click")
            show_message("Injection not configured in this build.")

        # Create object to hold metadata and allow user input
        self.metadata = Metadata(CH_LIST)

        # dialogs: reference channel, average channel, units, cycle table
        self.reference_channel_dlg = ChannelMenu(self.data_source, self.metadata)
        self.reference_channel_dlg.ref_ch_signal.connect(self.reference_change)
        self.reference_channel_dlg.unit_to_ru_signal.connect(self.unit_to_nm)
        self.reference_channel_dlg.unit_to_nm_signal.connect(self.unit_to_nm)
        self.reference_channel_dlg.cycle_marker_style_signal.connect(
            self.cycle_marker_style_changed,
        )
        if self.data_source == "static":
            # Disable filter for static data by unchecking the filter checkbox
            self.reference_channel_dlg.ui.filt_en.setChecked(False)

        # Create cycle table dialog (popup window)
        self.table_dialog = CycleTableDialog(self)
        self.table_dialog.set_segment_data(self.saved_segments, self.deleted_segment)
        self.table_dialog.row_deleted_sig.connect(self.delete_row)
        self.table_dialog.row_restored_sig.connect(self.restore_deleted)
        self.table_dialog.cell_edited_sig.connect(self.enter_edit_mode)
        self.table_dialog.table_toggled_sig.connect(self.toggle_table_style)

        # update segment data when cursor positions changed
        self.full_segment_view.segment_signal.connect(self.update_segment)

        # Connect shift values signal to update display box
        if hasattr(self.full_segment_view, "shift_values_signal"):
            self.full_segment_view.shift_values_signal.connect(
                self.update_shift_display_box,
            )

        # channel display options changed in full segment plot
        for ch in CH_LIST:
            getattr(self.ui, f"segment_{ch.upper()}").stateChanged.connect(
                partial(self.full_segment_view.display_channel_changed, ch),
            )
            getattr(self.ui, f"segment_{ch.upper()}").stateChanged.connect(
                partial(self.SOI_view.display_channel_changed, ch),
            )

        # Wire GraphContainer channel toggle buttons (Cycle of Interest title row)
        # These mirror the segment_A/B/C/D checkboxes but live in the graph header.
        if hasattr(self, "soi_frame") and self.soi_frame.channel_toggles:
            for ch, btn in self.soi_frame.channel_toggles.items():
                ch_lower = ch.lower()
                btn.toggled.connect(
                    partial(self.full_segment_view.display_channel_changed, ch_lower),
                )
                btn.toggled.connect(
                    partial(self.SOI_view.display_channel_changed, ch_lower),
                )
                # Keep legacy UI checkboxes in sync
                ui_cb_name = f"segment_{ch}"
                if hasattr(self.ui, ui_cb_name):
                    ui_cb = getattr(self.ui, ui_cb_name)
                    btn.toggled.connect(
                        lambda checked, cb=ui_cb: (
                            cb.blockSignals(True),
                            cb.setChecked(checked),
                            cb.blockSignals(False),
                        )
                    )

            # Wire reference channel Ctrl+click → DataWindow.reference_change
            def _on_soi_ref_changed(ch_letter):
                # ch_letter is lowercase or None
                self.reference_change(ch_letter if ch_letter else "None")
                # Keep set_reference dialog in sync too
                self.set_reference(ch_letter)

            self.soi_frame._on_ref_channel_changed = _on_soi_ref_changed

        # Connect right-side display checkboxes (if they exist)
        for ch in CH_LIST:
            right_checkbox_name = f"segment_{ch.upper()}_right"
            if hasattr(self.ui, right_checkbox_name):
                getattr(self.ui, right_checkbox_name).stateChanged.connect(
                    partial(self.full_segment_view.display_channel_changed, ch),
                )
                getattr(self.ui, right_checkbox_name).stateChanged.connect(
                    partial(self.SOI_view.display_channel_changed, ch),
                )
                # Sync left and right checkboxes
                getattr(self.ui, f"segment_{ch.upper()}").stateChanged.connect(
                    lambda state, cb_name=right_checkbox_name: (
                        getattr(self.ui, cb_name).blockSignals(True),
                        getattr(self.ui, cb_name).setChecked(
                            state == Qt.CheckState.Checked,
                        ),
                        getattr(self.ui, cb_name).blockSignals(False),
                    ),
                )
                getattr(self.ui, right_checkbox_name).stateChanged.connect(
                    lambda state, ch_name=ch: (
                        getattr(self.ui, f"segment_{ch_name.upper()}").blockSignals(
                            True,
                        ),
                        getattr(self.ui, f"segment_{ch_name.upper()}").setChecked(
                            state == Qt.CheckState.Checked,
                        ),
                        getattr(self.ui, f"segment_{ch_name.upper()}").blockSignals(
                            False,
                        ),
                    ),
                )

        if isinstance(self.ui, Ui_Processing):
            for ch in CH_LIST:
                getattr(self.ui, f"SOI_{ch.upper()}").toggled.connect(
                    getattr(self.ui, f"segment_{ch.upper()}").setChecked,
                )
                getattr(self.ui, f"segment_{ch.upper()}").toggled.connect(
                    getattr(self.ui, f"SOI_{ch.upper()}").setChecked,
                )

        # save segment button
        self.ui.save_segment_btn.clicked.connect(self.save_segment)

        # new segment button - now opens cycle data table
        if isinstance(self.ui, Ui_Sensorgram):
            self.ui.new_segment_btn.clicked.connect(self.open_cycle_table)
        else:
            self.ui.new_segment_btn.clicked.connect(self.new_segment)

        if isinstance(self.ui, Ui_Sensorgram) and hasattr(self.ui, "reset_segment_btn"):
            self.ui.reset_segment_btn.hide()
        elif hasattr(self.ui, "reset_segment_btn"):
            self.ui.reset_segment_btn.clicked.connect(self.reset_graphs)

        # clear graph button (only in sensorgram UI)
        if isinstance(self.ui, Ui_Sensorgram):
            # Connect sidebar Clear Graph button if it exists
            if hasattr(self, "clear_graph_btn_sidebar"):
                self.clear_graph_btn_sidebar.clicked.connect(self.reset_graphs)

            # Legacy buttons (hidden)
            if hasattr(self.ui, "clear_graph_btn"):
                self.ui.clear_graph_btn.clicked.connect(self.reset_graphs)

            # Connect Clear button in Sensorgram graph (top-left)
            if (
                hasattr(self.full_segment_view, "clear_button")
                and self.full_segment_view.clear_button
            ):
                self.full_segment_view.clear_button.clicked.connect(self.reset_graphs)

            # Connect legend checkboxes in Cycle of Interest graph to sync with UI checkboxes
            if hasattr(self.SOI_view, "legend_checkboxes"):
                for ch in CH_LIST:
                    if ch in self.SOI_view.legend_checkboxes:
                        # When legend checkbox changes, update the UI checkbox
                        legend_cb = self.SOI_view.legend_checkboxes[ch]
                        ui_cb = getattr(self.ui, f"segment_{ch.upper()}")

                        # Legend checkbox -> UI checkbox
                        legend_cb.stateChanged.connect(
                            lambda state, ui_checkbox=ui_cb: (
                                ui_checkbox.blockSignals(True),
                                ui_checkbox.setChecked(
                                    state == Qt.CheckState.Checked.value,
                                ),
                                ui_checkbox.blockSignals(False),
                            ),
                        )

                        # UI checkbox -> Legend checkbox (already connected via display_channel_changed)

            # Connect adjust margins button
            if hasattr(self.ui, "adjust_margins_btn"):
                self.ui.adjust_margins_btn.clicked.connect(
                    self.open_margin_adjust_dialog,
                )
            # Connect adjust margins button
            if hasattr(self.ui, "adjust_margins_btn"):
                self.ui.adjust_margins_btn.clicked.connect(
                    self.open_margin_adjust_dialog,
                )

        # open cycle table dialog button (only in sensorgram UI)
        if isinstance(self.ui, Ui_Sensorgram):
            self.ui.open_table_btn.clicked.connect(self.open_cycle_table)

        # For processing UI, keep old table setup
        if isinstance(self.ui, Ui_Processing):
            # data table add/remove row
            self.ui.delete_row_btn.clicked.connect(self.delete_row)
            self.ui.add_row_btn.clicked.connect(self.restore_deleted)

            # Set up cycle type dropdown for column 8
            cycle_type_delegate = CycleTypeDelegate(self.ui.data_table)
            self.ui.data_table.setItemDelegateForColumn(8, cycle_type_delegate)

            # Set up text input delegates with character limits for name and note columns
            text_delegate_name = TextInputDelegate(self.ui.data_table)
            text_delegate_note = TextInputDelegate(self.ui.data_table)
            self.ui.data_table.setItemDelegateForColumn(
                0,
                text_delegate_name,
            )  # Name column
            self.ui.data_table.setItemDelegateForColumn(
                9,
                text_delegate_note,
            )  # Note column

            # data table
            self.ui.data_table.cellDoubleClicked.connect(self.enter_edit_mode)
            self.ui.data_table.cellClicked.connect(self.enter_view_mode)
            self.ui.table_toggle.clicked.connect(self.toggle_table_style)

            # Set up page indicator circles for table toggle
            self.ui.page_indicator.setScene(QGraphicsScene())
            self.circles = (
                QGraphicsEllipseItem(-4, 0, 5, 5),
                QGraphicsEllipseItem(4, 0, 5, 5),
            )
            for c in self.circles:
                self.ui.page_indicator.scene().addItem(c)

            # Initialize table manager (handles table operations)
            self.table_manager = CycleTableManager(
                table_widget=self.ui.data_table,
                toggle_indicators=self.circles,
            )

        # Reference channel is now handled via Ctrl+click on the graph header buttons
        # (soi_frame.channel_toggles). Hide the legacy dialog button.
        if isinstance(self.ui, Ui_Processing):
            self.ui.reference_channel_btn.clicked.connect(
                self.open_reference_channel_dlg,
            )
            self.ui.reference_channel_btn.hide()

        # text fields
        self.ui.left_cursor_time.returnPressed.connect(self.update_left)
        self.ui.right_cursor_time.returnPressed.connect(self.update_right)

        # Initialize cycle manager (handles cycle type/time logic)
        # Only Processing UI has cycle type/time dropdowns
        if isinstance(self.ui, Ui_Processing):
            self.cycle_manager = CycleManager(
                cycle_type_dropdown=self.ui.current_cycle_type,
                cycle_time_dropdown=self.ui.current_cycle_time,
                sensorgram_graph=self.full_segment_view,
            )
        else:
            # Sensorgram doesn't have cycle controls in UI
            self.cycle_manager = None

        # Note: table_manager only exists for Ui_Processing, sensorgram uses table_dialog
        self.enable_controls(data_ready=False)

        # live view and reset segment button if dynamic window, imports if static window
        if self.data_source == "dynamic" and isinstance(self.ui, Ui_Sensorgram):
            self.ui.live_btn.setChecked(True)
            self.ui.live_btn.clicked.connect(self.toggle_view)
            self.reference_channel_dlg.ui.export_data.clicked.connect(
                self.export_trigger,
            )

        elif isinstance(self.ui, Ui_Processing):
            self.ui.export_raw_data_btn.clicked.connect(self.export_raw_data)
            self.ui.export_table_btn.clicked.connect(self.export_table)

            # Add Excel export button next to raw data export
            self.export_excel_btn = QPushButton(self.ui.export_raw_data_btn.parent())
            self.export_excel_btn.setObjectName("export_excel_btn")
            self.export_excel_btn.setText("📊 Excel")
            self.export_excel_btn.setToolTip("Export data to Excel format (.xlsx)")
            self.export_excel_btn.setStyleSheet(
                "QPushButton {"
                "  background: #1E8E3E;"
                "  color: white;"
                "  border: none;"
                "  border-radius: 8px;"
                "  padding: 8px 16px;"
                "  font-size: 13px;"
                "  font-weight: 600;"
                "  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                "}"
                "QPushButton:hover {"
                "  background: #188038;"
                "}"
                "QPushButton:pressed {"
                "  background: #0F5C26;"
                "}",
            )
            # Position it near the export button
            raw_btn_geom = self.ui.export_raw_data_btn.geometry()
            self.export_excel_btn.setGeometry(
                raw_btn_geom.x() + 35,
                raw_btn_geom.y(),
                70,
                30,
            )
            self.export_excel_btn.clicked.connect(self.export_to_excel)

            self.ui.import_sens_btn.clicked.connect(self.pull_from_sensorgram)
            self.ui.import_raw_data_btn.clicked.connect(self.import_raw_data)
            self.ui.import_table_btn.clicked.connect(self.import_table)
            self.ui.new_segment_btn.clicked.connect(self.start_from_last_seg)

        self.new_segment()

        # Move display groupBox to Graphic Control tab in sidebar
        if self.sidebar is not None and isinstance(self.ui, Ui_Sensorgram):
            # Get the Graphic Control tab
            graphic_control_tab = None
            for i in range(self.sidebar.tabWidget.count()):
                if self.sidebar.tabWidget.tabText(i) == "Graphic Control":
                    graphic_control_tab = self.sidebar.tabWidget.widget(i)
                    break

            if graphic_control_tab and hasattr(self.ui, "groupBox"):
                # The tab content is wrapped in a QScrollArea
                scroll_area = graphic_control_tab.findChild(QScrollArea)
                if scroll_area:
                    # Get the content widget inside the scroll area
                    content_widget = scroll_area.widget()
                    if content_widget:
                        layout = content_widget.layout()
                        if layout:
                            # Remove groupBox from its current parent
                            self.ui.groupBox.setParent(None)
                            # Insert display groupBox after clear button, before stretch
                            # Layout structure: clear_container, stretch
                            # We want: clear_container, groupBox, stretch
                            if layout.count() > 0:
                                # Remove the stretch temporarily
                                stretch_item = None
                                for i in range(layout.count()):
                                    item = layout.itemAt(i)
                                    if item and item.spacerItem():
                                        stretch_item = layout.takeAt(i)
                                        break

                                # Add groupBox
                                layout.addWidget(self.ui.groupBox)

                                # Re-add stretch at the end
                                if stretch_item:
                                    layout.addItem(stretch_item)
                                else:
                                    layout.addStretch()

        # Add settings panel to Settings tab in sidebar
        if self.sidebar is not None:
            from affilabs.widgets.settings_panel import SettingsPanel

            settings_panel = SettingsPanel()
            settings_panel.adjust_margins_requested.connect(
                self.open_margin_adjust_dialog,
            )
            settings_tab = self.sidebar.get_settings_tab()
            if settings_tab:
                layout = settings_tab.layout()
                if layout:
                    # Clear placeholder
                    while layout.count():
                        item = layout.takeAt(0)
                        if item.widget():
                            item.widget().deleteLater()
                    # Add settings panel
                    settings_panel.setParent(settings_tab)
                    layout.addWidget(settings_panel)

            # Add data export panel to Data tab (for sensorgram)
            if isinstance(self.ui, Ui_Sensorgram):
                from affilabs.widgets.data_panel import DataPanel

                self.data_panel = DataPanel()
                self.data_panel.export_triggered.connect(self.export_trigger)
                self.data_panel.export_excel_triggered.connect(self.export_to_excel)
                data_tab = self.sidebar.get_data_tab()
                if data_tab:
                    layout = data_tab.layout()
                    if layout:
                        # Clear placeholder
                        while layout.count():
                            item = layout.takeAt(0)
                            if item.widget():
                                item.widget().deleteLater()
                        # Add data panel
                        self.data_panel.setParent(data_tab)
                        layout.addWidget(self.data_panel)

        # Add text box validators
        self.ui.left_cursor_time.setValidator(QDoubleValidator())
        self.ui.right_cursor_time.setValidator(QDoubleValidator())
        if isinstance(self.ui, Ui_Sensorgram):
            self.ui.flow_rate.setValidator(QDoubleValidator(-60000, 60000, 1))

        # Circles for page indicator already created before table_manager initialization

        # Set up valve indicator diagram
        if isinstance(self.ui, Ui_Sensorgram):
            self.ui.loop_diagram.setScene(QGraphicsScene())

            # Reduced size: 80x80 (was 100x100)
            self.loop = QGraphicsEllipseItem(0, 0, 80, 80)
            self.loop_line = QGraphicsLineItem(-15, 0, 95, 0)
            self.sensor_line = QGraphicsLineItem(-15, 95, 95, 95)
            self.loop_label = QGraphicsSimpleTextItem("Loop")
            self.sensor_label = QGraphicsSimpleTextItem("Sensor")

            # Create modern styled pens with rounded caps (thinner: 5px instead of 6px)
            loop_pen = QPen(LOOP_BRUSH, 5)
            loop_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            sensor_pen = QPen(SENSOR_BRUSH, 5)
            sensor_pen.setCapStyle(Qt.PenCapStyle.RoundCap)

            self.loop.setPen(loop_pen)
            self.loop_line.setPen(loop_pen)
            self.sensor_line.setPen(sensor_pen)

            # Smaller font: 10pt instead of 12pt
            font = self.loop_label.font()
            font.setPointSize(10)
            font.setWeight(QFont.Weight.Medium)

            self.loop_label.setFont(font)
            self.loop_label.setBrush(LOOP_BRUSH)
            self.loop_label.setPos(100, -10)

            self.sensor_label.setFont(font)
            self.sensor_label.setBrush(SENSOR_BRUSH)
            self.sensor_label.setPos(100, 85)

            self.ui.loop_diagram.scene().addItem(self.loop)
            self.ui.loop_diagram.scene().addItem(self.loop_line)
            self.ui.loop_diagram.scene().addItem(self.sensor_line)
            self.ui.loop_diagram.scene().addItem(self.loop_label)
            self.ui.loop_diagram.scene().addItem(self.sensor_label)

        # Table manager initialized above with default Tab 1 view
        # (no need for separate hide_columns variable)

        # Hide progress bar until injection
        if isinstance(self.ui, Ui_Sensorgram):
            self.ui.progress_bar.hide()
            self.progress_bar_timer.setTimerType(Qt.TimerType.PreciseTimer)
            self.progress_bar_timer.setInterval(PROGRESS_BAR_UPDATE_TIME)
            self.progress_bar_timer.timeout.connect(self.increment_progress_bar)
