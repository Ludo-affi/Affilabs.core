"""Menu for setting reference channel, data filtering, and units."""


from typing import Literal, Self

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QWidget

from ui.ui_channelmenu import Ui_ChannelMenu
from widgets.metadata import Metadata


class ChannelMenu(QWidget):
    """Menu for setting reference channel, data filtering, and units."""

    ref_ch_signal = Signal(str)
    unit_to_ru_signal = Signal()
    unit_to_nm_signal = Signal()
    live_filt_sig = Signal(bool, int)
    proc_filt_sig = Signal(bool, int)
    colorblind_mode_signal = Signal(bool)

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
        self.ui.filt_en.toggled.connect(self.filtering_change)
        self.ui.filt_win.returnPressed.connect(self.filtering_change)
        self.ui.colorblind_mode.toggled.connect(self.colorblind_mode_change)
        self.ref_ch = "no ref"
        self.datawindow_type = datawindow_type

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

    def reference_ch_a(self: Self) -> None:
        """Set channel A as the reference channel."""
        if self.ui.channelA.isChecked():
            self.ref_ch_signal.emit("a")
            self.ref_ch = "a"

    def reference_ch_b(self: Self) -> None:
        """Set channel B as the reference channel."""
        if self.ui.channelB.isChecked():
            self.ref_ch_signal.emit("b")
            self.ref_ch = "b"

    def reference_ch_c(self: Self) -> None:
        """Set channel C as the reference channel."""
        if self.ui.channelC.isChecked():
            self.ref_ch_signal.emit("c")
            self.ref_ch = "c"

    def reference_ch_d(self: Self) -> None:
        """Set channel D as the reference channel."""
        if self.ui.channelD.isChecked():
            self.ref_ch_signal.emit("d")
            self.ref_ch = "d"

    def reference_ch_none(self: Self) -> None:
        """Remove any reference channel."""
        if self.ui.noRef.isChecked():
            self.ref_ch_signal.emit("None")
            self.ref_ch = "no ref"

    def unit_change_ru(self: Self) -> None:
        """Change units to RU."""
        self.unit_to_ru_signal.emit()
        self.ui.noRef.setChecked(True)  # noqa: FBT003

    def unit_change_nm(self: Self) -> None:
        """Change units to nm."""
        self.unit_to_nm_signal.emit()
        self.ui.noRef.setChecked(True)  # noqa: FBT003

    def filtering_change(self: Self) -> None:
        """Change data filtering window."""
        try:
            # Validate and sanitize input
            filt_win_text = self.ui.filt_win.text().strip()
            if not filt_win_text:
                # If empty, reset to default
                self.ui.filt_win.setText("3")
                return
            
            filt_win = int(filt_win_text)
            
            # Clamp to valid range
            if filt_win < 3:
                filt_win = 3
                self.ui.filt_win.setText("3")
            elif filt_win > 51:
                filt_win = 51
                self.ui.filt_win.setText("51")
            
            # Emit signal with validated value
            if self.datawindow_type == "dynamic":
                self.live_filt_sig.emit(
                    self.ui.filt_en.isChecked(),
                    filt_win,
                )
            else:
                self.proc_filt_sig.emit(
                    self.ui.filt_en.isChecked(),
                    filt_win,
                )
        except ValueError:
            # If not a valid integer, reset to default
            self.ui.filt_win.setText("3")

    def colorblind_mode_change(self: Self) -> None:
        """Toggle colorblind-friendly color palette."""
        self.colorblind_mode_signal.emit(self.ui.colorblind_mode.isChecked())

    def show(self: Self) -> None:
        """Re-adds the metadata menu to this menu."""
        # When the user saves raw data it will bring up a prompt containing the
        # metadata menu, this "steals" the widget away from this menu, so we
        # readd it whenever we show the menu to make sure it's actually there.
        # There may be a beter way to do this, but this seems to work.
        self.metadata_layout.addWidget(self.metadata)
        super().show()
