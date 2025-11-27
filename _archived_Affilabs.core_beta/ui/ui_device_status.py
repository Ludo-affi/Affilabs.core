# -*- coding: utf-8 -*-

################################################################################
## Device Status Display Widget
##
## Shows connection status for SPR device, AffiPump, and system capacity
################################################################################

from PySide6.QtCore import (QCoreApplication, QMetaObject, QRect, QSize, Qt)
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QSizePolicy, QSpacerItem, QVBoxLayout, QWidget)


class Ui_DeviceStatus(object):
    def setupUi(self, DeviceStatus):
        if not DeviceStatus.objectName():
            DeviceStatus.setObjectName(u"DeviceStatus")
        DeviceStatus.resize(340, 260)
        DeviceStatus.setMinimumSize(QSize(300, 200))

        font = QFont()
        font.setFamilies([u"Segoe UI"])
        DeviceStatus.setFont(font)

        self.verticalLayout = QVBoxLayout(DeviceStatus)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)

        # === Main Container Frame with Title ===
        self.main_container = QFrame(DeviceStatus)
        self.main_container.setObjectName(u"main_container")
        self.main_container.setFixedSize(305, 350)
        self.main_container.setFrameShape(QFrame.StyledPanel)
        self.main_container.setFrameShadow(QFrame.Raised)
        self.main_container.setStyleSheet(u"QFrame#main_container {\n"
            "    background-color: white;\n"
            "    border: 1px solid rgb(180, 180, 180);\n"
            "    border-radius: 8px;\n"
            "}")

        self.main_layout = QVBoxLayout(self.main_container)
        self.main_layout.setSpacing(8)
        self.main_layout.setObjectName(u"main_layout")
        self.main_layout.setContentsMargins(12, 12, 12, 12)

        # Main Title
        self.main_title = QLabel(self.main_container)
        self.main_title.setObjectName(u"main_title")
        font_main_title = QFont()
        font_main_title.setFamilies([u"Segoe UI"])
        font_main_title.setPointSize(11)
        font_main_title.setBold(True)
        self.main_title.setFont(font_main_title)
        self.main_title.setStyleSheet(u"QLabel {\n"
            "    color: rgb(30, 30, 30);\n"
            "    background-color: transparent;\n"
            "    padding-bottom: 5px;\n"
            "}")
        self.main_title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.main_layout.addWidget(self.main_title)

        # === SPR Device Section ===
        self.spr_frame = QFrame(self.main_container)
        self.spr_frame.setObjectName(u"spr_frame")
        self.spr_frame.setFrameShape(QFrame.StyledPanel)
        self.spr_frame.setFrameShadow(QFrame.Raised)
        self.spr_frame.setStyleSheet(u"QFrame#spr_frame {\n"
            "    background-color: rgb(250, 250, 250);\n"
            "    border: 1px solid rgb(200, 200, 200);\n"
            "    border-radius: 5px;\n"
            "}")

        self.spr_layout = QVBoxLayout(self.spr_frame)
        self.spr_layout.setSpacing(6)
        self.spr_layout.setObjectName(u"spr_layout")
        self.spr_layout.setContentsMargins(8, 8, 8, 8)

        # SPR Title
        self.spr_title = QLabel(self.spr_frame)
        self.spr_title.setObjectName(u"spr_title")
        font_title = QFont()
        font_title.setFamilies([u"Segoe UI"])
        font_title.setPointSize(10)
        font_title.setBold(True)
        self.spr_title.setFont(font_title)
        self.spr_title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.spr_layout.addWidget(self.spr_title)

        # SPR Device Status Row
        self.spr_device_layout = QHBoxLayout()
        self.spr_device_layout.setSpacing(8)
        self.spr_device_layout.setObjectName(u"spr_device_layout")

        self.spr_device_label = QLabel(self.spr_frame)
        self.spr_device_label.setObjectName(u"spr_device_label")
        font_normal = QFont()
        font_normal.setFamilies([u"Segoe UI"])
        font_normal.setPointSize(9)
        self.spr_device_label.setFont(font_normal)
        self.spr_device_label.setMinimumWidth(45)
        self.spr_device_layout.addWidget(self.spr_device_label)

        self.spr_device_indicator = QLabel(self.spr_frame)
        self.spr_device_indicator.setObjectName(u"spr_device_indicator")
        self.spr_device_indicator.setMinimumSize(QSize(10, 10))
        self.spr_device_indicator.setMaximumSize(QSize(10, 10))
        self.spr_device_indicator.setStyleSheet(u"QLabel {\n"
            "    background-color: rgb(200, 200, 200);\n"
            "    border-radius: 5px;\n"
            "}")
        self.spr_device_layout.addWidget(self.spr_device_indicator)

        self.spr_device_status = QLabel(self.spr_frame)
        self.spr_device_status.setObjectName(u"spr_device_status")
        self.spr_device_status.setFont(font_normal)
        self.spr_device_layout.addWidget(self.spr_device_status)

        spacer_spr_device = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.spr_device_layout.addItem(spacer_spr_device)

        self.spr_layout.addLayout(self.spr_device_layout)

        # Pump Status Row
        self.pump_layout = QHBoxLayout()
        self.pump_layout.setSpacing(8)
        self.pump_layout.setObjectName(u"pump_layout")

        self.pump_label = QLabel(self.spr_frame)
        self.pump_label.setObjectName(u"pump_label")
        self.pump_label.setFont(font_normal)
        self.pump_label.setMinimumWidth(45)
        self.pump_layout.addWidget(self.pump_label)

        self.pump_indicator = QLabel(self.spr_frame)
        self.pump_indicator.setObjectName(u"pump_indicator")
        self.pump_indicator.setMinimumSize(QSize(10, 10))
        self.pump_indicator.setMaximumSize(QSize(10, 10))
        self.pump_indicator.setStyleSheet(u"QLabel {\n"
            "    background-color: rgb(200, 200, 200);\n"
            "    border-radius: 5px;\n"
            "}")
        self.pump_layout.addWidget(self.pump_indicator)

        self.pump_status = QLabel(self.spr_frame)
        self.pump_status.setObjectName(u"pump_status")
        self.pump_status.setFont(font_normal)
        self.pump_layout.addWidget(self.pump_status)

        spacer_pump = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.pump_layout.addItem(spacer_pump)

        self.spr_layout.addLayout(self.pump_layout)

        # Connect Button Row
        self.connect_btn_layout = QHBoxLayout()
        self.connect_btn_layout.setSpacing(0)
        self.connect_btn_layout.setObjectName(u"connect_btn_layout")

        spacer_btn_left = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.connect_btn_layout.addItem(spacer_btn_left)

        self.spr_connect_btn = QPushButton(self.spr_frame)
        self.spr_connect_btn.setObjectName(u"spr_connect_btn")
        self.spr_connect_btn.setMinimumSize(QSize(80, 25))
        self.spr_connect_btn.setGeometry(180, 40, 80, 25)
        self.spr_connect_btn.setStyleSheet(u"QPushButton {\n"
            "    background-color: rgb(46, 48, 227);\n"
            "    color: white;\n"
            "    border: 1px solid rgb(46, 48, 227);\n"
            "    border-radius: 3px;\n"
            "    font-weight: bold;\n"
            "}\n"
            "QPushButton:hover {\n"
            "    background-color: rgb(66, 68, 247);\n"
            "}\n"
            "QPushButton:pressed {\n"
            "    background-color: rgb(26, 28, 207);\n"
            "}")
        # Button now uses absolute positioning, not in layout

        spacer_btn_right = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.connect_btn_layout.addItem(spacer_btn_right)

        self.spr_layout.addLayout(self.connect_btn_layout)

        self.main_layout.addWidget(self.spr_frame)

        # === Operation Section ===
        self.operation_frame = QFrame(self.main_container)
        self.operation_frame.setObjectName(u"operation_frame")
        self.operation_frame.setFrameShape(QFrame.StyledPanel)
        self.operation_frame.setFrameShadow(QFrame.Raised)
        self.operation_frame.setStyleSheet(u"QFrame#operation_frame {\n"
            "    background-color: rgb(250, 250, 250);\n"
            "    border: 1px solid rgb(200, 200, 200);\n"
            "    border-radius: 5px;\n"
            "}")

        self.operation_layout = QVBoxLayout(self.operation_frame)
        self.operation_layout.setSpacing(6)
        self.operation_layout.setObjectName(u"operation_layout")
        self.operation_layout.setContentsMargins(8, 8, 8, 8)

        # Operation Title
        self.operation_title = QLabel(self.operation_frame)
        self.operation_title.setObjectName(u"operation_title")
        self.operation_title.setFont(font_title)
        self.operation_title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.operation_layout.addWidget(self.operation_title)

        # Operation Mode Layout (horizontal for multiple modes)
        self.operation_modes_layout = QHBoxLayout()
        self.operation_modes_layout.setSpacing(5)
        self.operation_modes_layout.setObjectName(u"operation_modes_layout")

        # Static Mode Label
        self.static_mode_label = QLabel(self.operation_frame)
        self.static_mode_label.setObjectName(u"static_mode_label")
        font_mode = QFont()
        font_mode.setFamilies([u"Segoe UI"])
        font_mode.setPointSize(10)
        font_mode.setBold(False)
        self.static_mode_label.setFont(font_mode)
        self.static_mode_label.setStyleSheet(u"QLabel {\n"
            "    color: rgb(100, 100, 100);\n"
            "    background-color: transparent;\n"
            "    padding: 3px 8px;\n"
            "    border-radius: 3px;\n"
            "}")
        self.static_mode_label.setAlignment(Qt.AlignCenter)
        self.operation_modes_layout.addWidget(self.static_mode_label)

        # Flow Mode Label
        self.flow_mode_label = QLabel(self.operation_frame)
        self.flow_mode_label.setObjectName(u"flow_mode_label")
        self.flow_mode_label.setFont(font_mode)
        self.flow_mode_label.setStyleSheet(u"QLabel {\n"
            "    color: rgb(100, 100, 100);\n"
            "    background-color: transparent;\n"
            "    padding: 3px 8px;\n"
            "    border-radius: 3px;\n"
            "}")
        self.flow_mode_label.setAlignment(Qt.AlignCenter)
        self.operation_modes_layout.addWidget(self.flow_mode_label)

        # Not Supported Label
        self.not_supported_label = QLabel(self.operation_frame)
        self.not_supported_label.setObjectName(u"not_supported_label")
        self.not_supported_label.setFont(font_mode)
        self.not_supported_label.setStyleSheet(u"QLabel {\n"
            "    color: rgb(100, 100, 100);\n"
            "    background-color: transparent;\n"
            "    padding: 3px 8px;\n"
            "    border-radius: 3px;\n"
            "}")
        self.not_supported_label.setAlignment(Qt.AlignCenter)
        self.not_supported_label.setVisible(False)
        self.operation_modes_layout.addWidget(self.not_supported_label)

        self.operation_layout.addLayout(self.operation_modes_layout)

        self.main_layout.addWidget(self.operation_frame)

        # === System Status Section ===
        self.system_frame = QFrame(self.main_container)
        self.system_frame.setObjectName(u"system_frame")
        self.system_frame.setFrameShape(QFrame.StyledPanel)
        self.system_frame.setFrameShadow(QFrame.Raised)
        self.system_frame.setStyleSheet(u"QFrame#system_frame {\n"
            "    background-color: rgb(250, 250, 250);\n"
            "    border: 1px solid rgb(200, 200, 200);\n"
            "    border-radius: 5px;\n"
            "}")

        self.system_layout = QVBoxLayout(self.system_frame)
        self.system_layout.setSpacing(6)
        self.system_layout.setObjectName(u"system_layout")
        self.system_layout.setContentsMargins(8, 8, 8, 8)

        # System Title
        self.system_title = QLabel(self.system_frame)
        self.system_title.setObjectName(u"system_title")
        self.system_title.setFont(font_title)
        self.system_title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.system_layout.addWidget(self.system_title)

        # Sensor Status Row
        self.sensor_status_layout = QHBoxLayout()
        self.sensor_status_layout.setSpacing(10)
        self.sensor_status_layout.setObjectName(u"sensor_status_layout")

        self.sensor_label = QLabel(self.system_frame)
        self.sensor_label.setObjectName(u"sensor_label")
        self.sensor_label.setFont(font_normal)
        self.sensor_label.setMinimumWidth(70)
        self.sensor_status_layout.addWidget(self.sensor_label)

        self.sensor_status_indicator = QLabel(self.system_frame)
        self.sensor_status_indicator.setObjectName(u"sensor_status_indicator")
        self.sensor_status_indicator.setMinimumSize(QSize(12, 12))
        self.sensor_status_indicator.setMaximumSize(QSize(12, 12))
        self.sensor_status_indicator.setStyleSheet(u"QLabel {\n"
            "    background-color: rgb(200, 200, 200);\n"
            "    border-radius: 6px;\n"
            "}")
        self.sensor_status_layout.addWidget(self.sensor_status_indicator)

        self.sensor_status_label = QLabel(self.system_frame)
        self.sensor_status_label.setObjectName(u"sensor_status_label")
        self.sensor_status_label.setFont(font_normal)
        self.sensor_status_layout.addWidget(self.sensor_status_label)

        spacer_sensor = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.sensor_status_layout.addItem(spacer_sensor)

        self.system_layout.addLayout(self.sensor_status_layout)

        # Optics Status Row
        self.optics_status_layout = QHBoxLayout()
        self.optics_status_layout.setSpacing(10)
        self.optics_status_layout.setObjectName(u"optics_status_layout")

        self.optics_label = QLabel(self.system_frame)
        self.optics_label.setObjectName(u"optics_label")
        self.optics_label.setFont(font_normal)
        self.optics_label.setMinimumWidth(70)
        self.optics_status_layout.addWidget(self.optics_label)

        self.optics_status_indicator = QLabel(self.system_frame)
        self.optics_status_indicator.setObjectName(u"optics_status_indicator")
        self.optics_status_indicator.setMinimumSize(QSize(12, 12))
        self.optics_status_indicator.setMaximumSize(QSize(12, 12))
        self.optics_status_indicator.setStyleSheet(u"QLabel {\n"
            "    background-color: rgb(200, 200, 200);\n"
            "    border-radius: 6px;\n"
            "}")
        self.optics_status_layout.addWidget(self.optics_status_indicator)

        self.optics_status_label = QLabel(self.system_frame)
        self.optics_status_label.setObjectName(u"optics_status_label")
        self.optics_status_label.setFont(font_normal)
        self.optics_status_layout.addWidget(self.optics_status_label)

        spacer_optics = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.optics_status_layout.addItem(spacer_optics)

        self.system_layout.addLayout(self.optics_status_layout)

        # Fluidics Status Row
        self.fluidics_status_layout = QHBoxLayout()
        self.fluidics_status_layout.setSpacing(10)
        self.fluidics_status_layout.setObjectName(u"fluidics_status_layout")

        self.fluidics_label = QLabel(self.system_frame)
        self.fluidics_label.setObjectName(u"fluidics_label")
        self.fluidics_label.setFont(font_normal)
        self.fluidics_label.setMinimumWidth(70)
        self.fluidics_status_layout.addWidget(self.fluidics_label)

        self.fluidics_status_indicator = QLabel(self.system_frame)
        self.fluidics_status_indicator.setObjectName(u"fluidics_status_indicator")
        self.fluidics_status_indicator.setMinimumSize(QSize(12, 12))
        self.fluidics_status_indicator.setMaximumSize(QSize(12, 12))
        self.fluidics_status_indicator.setStyleSheet(u"QLabel {\n"
            "    background-color: rgb(200, 200, 200);\n"
            "    border-radius: 6px;\n"
            "}")
        self.fluidics_status_layout.addWidget(self.fluidics_status_indicator)

        self.fluidics_status_label = QLabel(self.system_frame)
        self.fluidics_status_label.setObjectName(u"fluidics_status_label")
        self.fluidics_status_label.setFont(font_normal)
        self.fluidics_status_layout.addWidget(self.fluidics_status_label)

        spacer_fluidics = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.fluidics_status_layout.addItem(spacer_fluidics)

        self.system_layout.addLayout(self.fluidics_status_layout)

        self.main_layout.addWidget(self.system_frame)

        # Add main container to widget
        self.verticalLayout.addWidget(self.main_container)

        # Add spacer before support link to push it to bottom
        spacer_before_support = QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.verticalLayout.addItem(spacer_before_support)

        # Support link at bottom
        self.support_link = QLabel(DeviceStatus)
        self.support_link.setObjectName(u"support_link")
        font_link = QFont()
        font_link.setFamilies([u"Segoe UI"])
        font_link.setPointSize(9)
        font_link.setUnderline(False)  # Remove underline from font, use CSS instead
        self.support_link.setFont(font_link)
        self.support_link.setStyleSheet(u"QLabel {\n"
            "    color: rgb(46, 48, 227);\n"
            "    background-color: transparent;\n"
            "    padding: 12px 0px;\n"
            "}\n"
            "QLabel a {\n"
            "    color: rgb(46, 48, 227);\n"
            "    text-decoration: none;\n"
            "}\n"
            "QLabel a:hover {\n"
            "    color: rgb(66, 68, 247);\n"
            "    text-decoration: underline;\n"
            "}")
        self.support_link.setAlignment(Qt.AlignCenter)
        self.support_link.setTextFormat(Qt.TextFormat.RichText)
        self.support_link.setOpenExternalLinks(True)
        self.verticalLayout.addWidget(self.support_link)

        self.retranslateUi(DeviceStatus)
        QMetaObject.connectSlotsByName(DeviceStatus)

    def retranslateUi(self, DeviceStatus):
        DeviceStatus.setWindowTitle(QCoreApplication.translate("DeviceStatus", u"Device Status", None))
        self.main_title.setText(QCoreApplication.translate("DeviceStatus", u"Hardware Status", None))
        self.spr_title.setText(QCoreApplication.translate("DeviceStatus", u"Device", None))
        self.spr_device_label.setText(QCoreApplication.translate("DeviceStatus", u"SPR:", None))
        self.spr_device_status.setText(QCoreApplication.translate("DeviceStatus", u"Not Connected", None))
        self.pump_label.setText(QCoreApplication.translate("DeviceStatus", u"Pump:", None))
        self.pump_status.setText(QCoreApplication.translate("DeviceStatus", u"Not Connected", None))
        self.spr_connect_btn.setText(QCoreApplication.translate("DeviceStatus", u"Connect", None))
        self.operation_title.setText(QCoreApplication.translate("DeviceStatus", u"Operation", None))
        self.static_mode_label.setText(QCoreApplication.translate("DeviceStatus", u"Static", None))
        self.flow_mode_label.setText(QCoreApplication.translate("DeviceStatus", u"Flow", None))
        self.not_supported_label.setText(QCoreApplication.translate("DeviceStatus", u"Not Supported", None))
        self.system_title.setText(QCoreApplication.translate("DeviceStatus", u"System Status", None))
        self.sensor_label.setText(QCoreApplication.translate("DeviceStatus", u"Sensor:", None))
        self.sensor_status_label.setText(QCoreApplication.translate("DeviceStatus", u"Unknown", None))
        self.optics_label.setText(QCoreApplication.translate("DeviceStatus", u"Optics:", None))
        self.optics_status_label.setText(QCoreApplication.translate("DeviceStatus", u"Unknown", None))
        self.fluidics_label.setText(QCoreApplication.translate("DeviceStatus", u"Fluidics:", None))
        self.fluidics_status_label.setText(QCoreApplication.translate("DeviceStatus", u"Unknown", None))
        self.support_link.setText(QCoreApplication.translate("DeviceStatus", u"<a href=\"https://www.affiniteinstruments.com/contact-us\">Support</a>", None))
