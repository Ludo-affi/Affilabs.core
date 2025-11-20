from PySide6.QtWidgets import QWidget

from ui.ui_sidebar import Ui_Sidebar
from widgets.device import Device
from widgets.kinetics import Kinetic


class Sidebar(QWidget):
    device_widget = None
    kinetic_widget = None

    def __init__(self):
        super().__init__()
        self.ui = Ui_Sidebar()
        self.ui.setupUi(self)

    def set_widgets(self):
        # Reuse existing widgets if they already exist (performance optimization)
        if self.device_widget is None:
            # display device widget on top
            self.device_widget = Device()
            self.device_widget.setParent(self.ui.device_frame)
            self.device_widget.show()

        if self.kinetic_widget is None:
            # display kinetic widget on bottom
            self.kinetic_widget = Kinetic()
            self.kinetic_widget.setParent(self.ui.kinetic_frame)
            self.kinetic_widget.show()
