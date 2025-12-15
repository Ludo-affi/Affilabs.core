"""Menu for setting reference channel, data filtering, and units."""

from typing import Literal, Self

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QRadioButton, QVBoxLayout, QWidget

from affilabs.ui.ui_channelmenu import Ui_ChannelMenu
from affilabs.utils.logger import logger
from affilabs.widgets.metadata import Metadata
from settings import settings


class ChannelMenu(QWidget):
    """Menu for setting reference channel, data filtering, and units."""

    ref_ch_signal = Signal(str)
    unit_to_ru_signal = Signal()
    unit_to_nm_signal = Signal()
    live_filt_sig = Signal(bool, int)
    proc_filt_sig = Signal(bool, int)
    colorblind_mode_signal = Signal(bool)
    cycle_marker_style_signal = Signal(str)  # "cursors" or "lines"

    def __init__(
        self: Self,
        datawindow_type: Literal["static", "dynamic"],
        metadata: Metadata,
    ) -> None:
        """Menu for setting reference channel, data filtering, and units."""
        super().__init__()

        # Sets the window title and icon
        self.setWindowTitle("Affinite Instruments")
        self.setWindowIcon(QIcon(":/img/img/affinite2.ico"))

        # Creates widget to hold the old menu
        self.data_settings = QWidget()

        self.ui = Ui_ChannelMenu()
        self.ui.setupUi(self.data_settings)
        self.ui.channelA.toggled.connect(self.reference_ch_a)
        self.ui.channelB.toggled.connect(self.reference_ch_b)
        self.ui.channelC.toggled.connect(self.reference_ch_c)
        self.ui.channelD.toggled.connect(self.reference_ch_d)
        self.ui.noRef.toggled.connect(self.reference_ch_none)
        self.ui.unit_nm.clicked.connect(self.unit_change_nm)
        self.ui.unit_ru.clicked.connect(self.unit_change_ru)
        self.ui.filt_en.toggled.connect(self.filter_enable_change)
        self.ui.filt_win.returnPressed.connect(self.filtering_window_change)
        self.ui.filt_win.editingFinished.connect(self.filtering_window_change)
        self.ui.colorblind_mode.toggled.connect(self.colorblind_mode_change)
        self.ref_ch = "no ref"
        self.datawindow_type = datawindow_type

        # Add cycle marker style selection
        self.cycle_marker_group = QGroupBox("Cycle Markers")
        self.cycle_marker_layout = QVBoxLayout(self.cycle_marker_group)

        self.marker_cursors = QRadioButton("Movable Cursors (Yellow/Red)")
        self.marker_lines = QRadioButton("Vertical Line Markers with Labels")

        # Set default based on settings
        if settings.CYCLE_MARKER_STYLE == "lines":
            self.marker_lines.setChecked(True)
        else:
            self.marker_cursors.setChecked(True)

        self.marker_cursors.toggled.connect(self.cycle_marker_change)
        self.marker_lines.toggled.connect(self.cycle_marker_change)

        self.cycle_marker_layout.addWidget(self.marker_cursors)
        self.cycle_marker_layout.addWidget(self.marker_lines)

        # Add to data settings layout (after colorblind mode)
        self.data_settings.layout().addWidget(self.cycle_marker_group)

        # Puts the metadata menu in a box, layout used to get proper spacing and sizing
        self.metadata_box = QGroupBox("TraceDrawer Metadata")
        self.metadata = metadata
        self.metadata_layout = QHBoxLayout(self.metadata_box)
        self.metadata_layout.addWidget(self.metadata)

        # Puts the old menu and the new metadata menu next to each other
        self.main_layout = QHBoxLayout(self)
        self.main_layout.addWidget(self.data_settings)
        self.main_layout.addWidget(self.metadata_box)
        self.main_layout.setSizeConstraint(QHBoxLayout.SizeConstraint.SetFixedSize)

    def _set_reference_channel(self: Self, channel: str, button_checked: bool) -> None:
        """Set reference channel (DRY helper method)."""
        if button_checked:
            emit_value = "None" if channel == "no ref" else channel
            self.ref_ch_signal.emit(emit_value)
            self.ref_ch = channel

    def reference_ch_a(self: Self) -> None:
        """Set channel A as the reference channel."""
        self._set_reference_channel("a", self.ui.channelA.isChecked())

    def reference_ch_b(self: Self) -> None:
        """Set channel B as the reference channel."""
        self._set_reference_channel("b", self.ui.channelB.isChecked())

    def reference_ch_c(self: Self) -> None:
        """Set channel C as the reference channel."""
        self._set_reference_channel("c", self.ui.channelC.isChecked())

    def reference_ch_d(self: Self) -> None:
        """Set channel D as the reference channel."""
        self._set_reference_channel("d", self.ui.channelD.isChecked())

    def reference_ch_none(self: Self) -> None:
        """Remove any reference channel."""
        self._set_reference_channel("no ref", self.ui.noRef.isChecked())

    def unit_change_ru(self: Self) -> None:
        """Change units to RU."""
        self.unit_to_ru_signal.emit()
        self.ui.noRef.setChecked(True)

    def unit_change_nm(self: Self) -> None:
        """Change units to nm."""
        self.unit_to_nm_signal.emit()
        self.ui.noRef.setChecked(True)

    def _validate_filter_window(self: Self) -> int:
        """Validate and clamp filter window size to valid range [3, 51]."""
        try:
            filt_win_text = self.ui.filt_win.text().strip()
            if not filt_win_text:
                filt_win = 3
            else:
                filt_win = int(filt_win_text)
                filt_win = max(3, min(51, filt_win))  # Clamp to [3, 51]

            self.ui.filt_win.setText(str(filt_win))
            return filt_win
        except ValueError:
            self.ui.filt_win.setText("3")
            return 3

    def _emit_filter_signal(self: Self, is_enabled: bool, window_size: int) -> None:
        """Emit appropriate filter signal based on datawindow type."""
        if self.datawindow_type == "dynamic":
            self.live_filt_sig.emit(is_enabled, window_size)
        else:
            self.proc_filt_sig.emit(is_enabled, window_size)

    def filter_enable_change(self: Self) -> None:
        """Handle filter enable/disable toggle."""
        is_enabled = self.ui.filt_en.isChecked()
        filt_win = self._validate_filter_window()
        self._emit_filter_signal(is_enabled, filt_win)

    def filtering_window_change(self: Self) -> None:
        """Handle filter window size change."""
        is_enabled = self.ui.filt_en.isChecked()
        filt_win = self._validate_filter_window()
        self._emit_filter_signal(is_enabled, filt_win)

    def colorblind_mode_change(self: Self) -> None:
        """Toggle colorblind-friendly color palette."""
        self.colorblind_mode_signal.emit(self.ui.colorblind_mode.isChecked())

    def cycle_marker_change(self: Self) -> None:
        """Change cycle marker style."""
        if self.marker_cursors.isChecked():
            style = "cursors"
        else:
            style = "lines"
        logger.info(f"📡 Emitting cycle marker style change signal: {style}")
        settings.CYCLE_MARKER_STYLE = style
        self.cycle_marker_style_signal.emit(style)

    def show(self: Self) -> None:
        """Re-adds the metadata menu to this menu."""
        # When the user saves raw data it will bring up a prompt containing the
        # metadata menu, this "steals" the widget away from this menu, so we
        # readd it whenever we show the menu to make sure it's actually there.
        # There may be a beter way to do this, but this seems to work.
        self.metadata_layout.addWidget(self.metadata)
        super().show()
