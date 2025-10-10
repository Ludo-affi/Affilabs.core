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
        # display device widget on top
        self.device_widget = Device()
        self.device_widget.setParent(self.ui.device_frame)

        # display kinetic widget on bottom
        self.kinetic_widget = Kinetic()
        self.kinetic_widget.setParent(self.ui.kinetic_frame)
