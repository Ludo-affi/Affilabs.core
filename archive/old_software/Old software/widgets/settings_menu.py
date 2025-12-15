"""Contains the widget and code for the settings menu of the ezControl app."""

from typing import Self

from PySide6.QtWidgets import QDialog, QTabWidget, QVBoxLayout, QWidget

from widgets.advanced import P4SPRAdvMenu
from widgets.channelmenu import ChannelMenu
from widgets.metadata import Metadata


class Settings(QDialog):
    """Settings menu widget."""

    spr_settings: QWidget
    """Contains settings for refence channel, data filtering and units. This is
    the widget from the origonal SPR settings menu from pre v2.3.
    """

    metadata: Metadata
    """Contains the TraceDrawer metadata settings."""

    advanced: P4SPRAdvMenu
    """Contains advanced settings set during calibration like LED intensities and
    integration time.
    """

    tabs: QTabWidget
    """Contains the other widgets in tabs."""

    main_layout: QVBoxLayout
    """Main layout of the widget."""

    def __init__(
        self: Self,
        spr_settings: ChannelMenu,
        advanced: P4SPRAdvMenu,
        parent: QWidget | None = None,
    ) -> None:
        """Create the settings menu."""
        super().__init__(parent)

        # Set window properties
        self.setWindowTitle("ezControl Settings")

        # Create sub-widgets
        self.spr_settings = spr_settings.data_settings
        self.metadata = spr_settings.metadata
        self.advanced = advanced
        self.tabs = QTabWidget()
        self.main_layout = QVBoxLayout(self)

        # Add widgets to layout
        self.main_layout.addWidget(self.tabs)

        # Add sub-widgets to tabs

        self.tabs.addTab(self.spr_settings, "SPR Settings")
        self.tabs.addTab(self.metadata, "TraceDrawer Metadata")
        self.tabs.addTab(self.advanced, "Advanced Settings")

        # Disable TraceDrawer tab
        trace_index = self.tabs.indexOf(self.metadata)
        if trace_index != -1:
            self.tabs.setTabEnabled(trace_index, False)


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication

    app = QApplication([])

    m = Metadata(list("ABCD"))
    c = ChannelMenu("dynamic", m)
    a = P4SPRAdvMenu()

    w = Settings(c, a)
    w.show()

    app.exec()
