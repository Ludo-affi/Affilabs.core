################################################################################
## Form generated from reading UI file 'device.ui'
##
## Created by: Qt User Interface Compiler version 6.6.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import QCoreApplication, QMetaObject, QSize
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)


class Ui_Device:
    def setupUi(self, Device):
        if not Device.objectName():
            Device.setObjectName("Device")
        Device.resize(275, 300)
        Device.setMinimumSize(QSize(275, 280))
        font = QFont()
        font.setFamilies(["Segoe UI"])
        Device.setFont(font)
        Device.setStyleSheet("")
        self.verticalLayout = QVBoxLayout(Device)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName("verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.controller_frame = QFrame(Device)
        self.controller_frame.setObjectName("controller_frame")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.controller_frame.sizePolicy().hasHeightForWidth()
        )
        self.controller_frame.setSizePolicy(sizePolicy)
        self.controller_frame.setMinimumSize(QSize(0, 100))
        self.controller_frame.setMaximumSize(QSize(16777215, 100))
        self.controller_frame.setFrameShape(QFrame.StyledPanel)
        self.controller_frame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout = QHBoxLayout(self.controller_frame)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.add_ctrl = QPushButton(self.controller_frame)
        self.add_ctrl.setObjectName("add_ctrl")
        self.add_ctrl.setMinimumSize(QSize(120, 25))
        self.add_ctrl.setStyleSheet(
            "QPushButton {\n"
            "		\n"
            "		background-color: rgb(230, 230, 230);\n"
            "	    border: 1px solid rgb(171, 171, 171); \n"
            "		border-radius: 3px;\n"
            "\n"
            "}\n"
            "\n"
            "QPushButton::hover{\n"
            "	background: rgb(253, 253, 253);\n"
            "	border: 1px raised;\n"
            "	border-radius: 5px;\n"
            "}"
        )

        self.horizontalLayout.addWidget(self.add_ctrl)

        self.horizontalSpacer_2 = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout.addItem(self.horizontalSpacer_2)

        self.verticalLayout.addWidget(self.controller_frame)

        self.kinetic_frame = QFrame(Device)
        self.kinetic_frame.setObjectName("kinetic_frame")
        sizePolicy.setHeightForWidth(
            self.kinetic_frame.sizePolicy().hasHeightForWidth()
        )
        self.kinetic_frame.setSizePolicy(sizePolicy)
        self.kinetic_frame.setMinimumSize(QSize(0, 100))
        self.kinetic_frame.setMaximumSize(QSize(16777215, 100))
        self.kinetic_frame.setFrameShape(QFrame.StyledPanel)
        self.kinetic_frame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_2 = QHBoxLayout(self.kinetic_frame)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer_3 = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout_2.addItem(self.horizontalSpacer_3)

        self.add_knx = QPushButton(self.kinetic_frame)
        self.add_knx.setObjectName("add_knx")
        self.add_knx.setMinimumSize(QSize(130, 25))
        self.add_knx.setStyleSheet(
            "QPushButton {\n"
            "		\n"
            "		background-color: rgb(230, 230, 230);\n"
            "	    border: 1px solid rgb(171, 171, 171); \n"
            "		border-radius: 3px;\n"
            "\n"
            "}\n"
            "\n"
            "QPushButton::hover{\n"
            "	background: rgb(253, 253, 253);\n"
            "	border: 1px raised;\n"
            "	border-radius: 5px;\n"
            "}"
        )

        self.horizontalLayout_2.addWidget(self.add_knx)

        self.horizontalSpacer_4 = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout_2.addItem(self.horizontalSpacer_4)

        self.verticalLayout.addWidget(self.kinetic_frame)

        self.pump_frame = QWidget(Device)
        self.pump_frame.setObjectName("pump_frame")
        sizePolicy.setHeightForWidth(self.pump_frame.sizePolicy().hasHeightForWidth())
        self.pump_frame.setSizePolicy(sizePolicy)
        self.pump_frame.setMinimumSize(QSize(0, 100))
        self.horizontalLayout_3 = QHBoxLayout(self.pump_frame)
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer_5 = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout_3.addItem(self.horizontalSpacer_5)

        self.add_pump = QPushButton(self.pump_frame)
        self.add_pump.setObjectName("add_pump")
        self.add_pump.setMinimumSize(QSize(120, 25))
        self.add_pump.setStyleSheet(
            "QPushButton {\n"
            "		\n"
            "		background-color: rgb(230, 230, 230);\n"
            "	    border: 1px solid rgb(171, 171, 171); \n"
            "		border-radius: 3px;\n"
            "\n"
            "}\n"
            "\n"
            "QPushButton::hover{\n"
            "	background: rgb(253, 253, 253);\n"
            "	border: 1px raised;\n"
            "	border-radius: 5px;\n"
            "}"
        )

        self.horizontalLayout_3.addWidget(self.add_pump)

        self.horizontalSpacer_6 = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout_3.addItem(self.horizontalSpacer_6)

        self.verticalLayout.addWidget(self.pump_frame)

        self.retranslateUi(Device)

        QMetaObject.connectSlotsByName(Device)

    # setupUi

    def retranslateUi(self, Device):
        Device.setWindowTitle(QCoreApplication.translate("Device", "Form", None))
        self.add_ctrl.setText(
            QCoreApplication.translate("Device", "Add SPR Device", None)
        )
        self.add_knx.setText(
            QCoreApplication.translate("Device", "Add Kinetic Device", None)
        )
        self.add_pump.setText(
            QCoreApplication.translate("Device", "Add Pump Device", None)
        )

    # retranslateUi
