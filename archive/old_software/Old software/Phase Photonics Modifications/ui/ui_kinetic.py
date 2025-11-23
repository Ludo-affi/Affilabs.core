# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'kinetic.ui'
##
## Created by: Qt User Interface Compiler version 6.6.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame,
    QGridLayout, QGroupBox, QLabel, QLayout,
    QPushButton, QRadioButton, QSizePolicy, QVBoxLayout,
    QWidget)
import ui.ai_rc

class Ui_Kinetic(object):
    def setupUi(self, Kinetic):
        if not Kinetic.objectName():
            Kinetic.setObjectName(u"Kinetic")
        Kinetic.resize(260, 440)
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(Kinetic.sizePolicy().hasHeightForWidth())
        Kinetic.setSizePolicy(sizePolicy)
        Kinetic.setMinimumSize(QSize(260, 440))
        Kinetic.setMaximumSize(QSize(262, 500))
        font = QFont()
        font.setFamilies([u"Segoe UI"])
        Kinetic.setFont(font)
        Kinetic.setStyleSheet(u"")
        self.gridLayout = QGridLayout(Kinetic)
        self.gridLayout.setSpacing(0)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_2 = QVBoxLayout()
        self.verticalLayout_2.setSpacing(2)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setSizeConstraint(QLayout.SetMinimumSize)
        self.CH1 = QGroupBox(Kinetic)
        self.CH1.setObjectName(u"CH1")
        self.CH1.setMinimumSize(QSize(255, 215))
        self.CH1.setMaximumSize(QSize(255, 215))
        font1 = QFont()
        font1.setFamilies([u"Segoe UI"])
        font1.setPointSize(8)
        self.CH1.setFont(font1)
        self.run1 = QPushButton(self.CH1)
        self.run1.setObjectName(u"run1")
        self.run1.setGeometry(QRect(10, 50, 81, 28))
        self.run1.setMinimumSize(QSize(40, 25))
        self.run1.setStyleSheet(u"QPushButton {\n"
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
"}")
        self.flush1 = QPushButton(self.CH1)
        self.flush1.setObjectName(u"flush1")
        self.flush1.setGeometry(QRect(10, 80, 81, 28))
        self.flush1.setMinimumSize(QSize(40, 25))
        self.flush1.setStyleSheet(u"QPushButton {\n"
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
"}")
        self.run_rate_ch1 = QComboBox(self.CH1)
        self.run_rate_ch1.addItem("")
        self.run_rate_ch1.addItem("")
        self.run_rate_ch1.addItem("")
        self.run_rate_ch1.addItem("")
        self.run_rate_ch1.setObjectName(u"run_rate_ch1")
        self.run_rate_ch1.setGeometry(QRect(110, 50, 71, 25))
        self.run_rate_ch1.setMinimumSize(QSize(40, 25))
        self.label = QLabel(self.CH1)
        self.label.setObjectName(u"label")
        self.label.setGeometry(QRect(190, 55, 50, 16))
        self.label.setMinimumSize(QSize(50, 16))
        self.label.setMaximumSize(QSize(50, 16))
        self.label.setPixmap(QPixmap(u":/img/img/micro_per_min.png"))
        self.label.setScaledContents(True)
        self.status1 = QLabel(self.CH1)
        self.status1.setObjectName(u"status1")
        self.status1.setGeometry(QRect(60, 20, 111, 21))
        self.label_15 = QLabel(self.CH1)
        self.label_15.setObjectName(u"label_15")
        self.label_15.setGeometry(QRect(10, 20, 55, 21))
        self.label_17 = QLabel(self.CH1)
        self.label_17.setObjectName(u"label_17")
        self.label_17.setGeometry(QRect(10, 190, 141, 16))
        self.inject_time_ch1 = QLabel(self.CH1)
        self.inject_time_ch1.setObjectName(u"inject_time_ch1")
        self.inject_time_ch1.setGeometry(QRect(150, 190, 71, 16))
        self.label_18 = QLabel(self.CH1)
        self.label_18.setObjectName(u"label_18")
        self.label_18.setGeometry(QRect(230, 190, 21, 16))
        self.label_18.setMinimumSize(QSize(10, 10))
        self.sync_1 = QCheckBox(self.CH1)
        self.sync_1.setObjectName(u"sync_1")
        self.sync_1.setEnabled(True)
        self.sync_1.setGeometry(QRect(170, 10, 81, 41))
        self.pump_flow_ch1 = QGroupBox(self.CH1)
        self.pump_flow_ch1.setObjectName(u"pump_flow_ch1")
        self.pump_flow_ch1.setGeometry(QRect(10, 120, 115, 65))
        self.spr_ch1 = QRadioButton(self.pump_flow_ch1)
        self.spr_ch1.setObjectName(u"spr_ch1")
        self.spr_ch1.setGeometry(QRect(30, 40, 81, 20))
        self.waste_ch1 = QRadioButton(self.pump_flow_ch1)
        self.waste_ch1.setObjectName(u"waste_ch1")
        self.waste_ch1.setGeometry(QRect(30, 20, 81, 20))
        self.waste_ch1.setChecked(True)
        self.sample_flow_ch1 = QGroupBox(self.CH1)
        self.sample_flow_ch1.setObjectName(u"sample_flow_ch1")
        self.sample_flow_ch1.setEnabled(True)
        self.sample_flow_ch1.setGeometry(QRect(130, 120, 115, 65))
        self.inject_ch1 = QRadioButton(self.sample_flow_ch1)
        self.inject_ch1.setObjectName(u"inject_ch1")
        self.inject_ch1.setGeometry(QRect(30, 40, 71, 20))
        self.load_ch1 = QRadioButton(self.sample_flow_ch1)
        self.load_ch1.setObjectName(u"load_ch1")
        self.load_ch1.setGeometry(QRect(30, 20, 71, 20))
        self.load_ch1.setChecked(True)
        self.sensor_frame_ch1 = QFrame(self.CH1)
        self.sensor_frame_ch1.setObjectName(u"sensor_frame_ch1")
        self.sensor_frame_ch1.setGeometry(QRect(100, 70, 151, 51))
        self.sensor_frame_ch1.setFrameShape(QFrame.StyledPanel)
        self.sensor_frame_ch1.setFrameShadow(QFrame.Raised)
        self.label_5 = QLabel(self.sensor_frame_ch1)
        self.label_5.setObjectName(u"label_5")
        self.label_5.setGeometry(QRect(100, 10, 50, 16))
        self.label_5.setMinimumSize(QSize(10, 10))
        self.label_5.setMaximumSize(QSize(50, 16))
        self.label_5.setPixmap(QPixmap(u":/img/img/micro_per_min.png"))
        self.label_5.setScaledContents(True)
        self.label_2 = QLabel(self.sensor_frame_ch1)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setGeometry(QRect(10, 10, 31, 16))
        self.label_2.setMinimumSize(QSize(10, 10))
        self.flow1 = QLabel(self.sensor_frame_ch1)
        self.flow1.setObjectName(u"flow1")
        self.flow1.setGeometry(QRect(50, 10, 41, 16))
        self.label_3 = QLabel(self.sensor_frame_ch1)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setGeometry(QRect(10, 30, 51, 16))
        self.temp1 = QLabel(self.sensor_frame_ch1)
        self.temp1.setObjectName(u"temp1")
        self.temp1.setGeometry(QRect(60, 30, 31, 16))
        self.label_11 = QLabel(self.sensor_frame_ch1)
        self.label_11.setObjectName(u"label_11")
        self.label_11.setGeometry(QRect(100, 30, 30, 16))
        self.label_11.setMinimumSize(QSize(30, 16))
        self.label_11.setMaximumSize(QSize(30, 16))
        self.label_11.setPixmap(QPixmap(u":/img/img/deg_c.png"))
        self.label_11.setScaledContents(True)

        self.verticalLayout_2.addWidget(self.CH1, 0, Qt.AlignHCenter)

        self.CH2 = QGroupBox(Kinetic)
        self.CH2.setObjectName(u"CH2")
        self.CH2.setMinimumSize(QSize(255, 215))
        self.CH2.setMaximumSize(QSize(255, 215))
        self.CH2.setFont(font)
        self.run2 = QPushButton(self.CH2)
        self.run2.setObjectName(u"run2")
        self.run2.setGeometry(QRect(10, 50, 81, 28))
        self.run2.setMinimumSize(QSize(40, 25))
        self.run2.setStyleSheet(u"QPushButton {\n"
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
"}")
        self.flush2 = QPushButton(self.CH2)
        self.flush2.setObjectName(u"flush2")
        self.flush2.setGeometry(QRect(10, 80, 81, 28))
        self.flush2.setMinimumSize(QSize(40, 25))
        self.flush2.setStyleSheet(u"QPushButton {\n"
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
"}")
        self.label_16 = QLabel(self.CH2)
        self.label_16.setObjectName(u"label_16")
        self.label_16.setGeometry(QRect(10, 20, 55, 21))
        self.status2 = QLabel(self.CH2)
        self.status2.setObjectName(u"status2")
        self.status2.setGeometry(QRect(60, 20, 111, 21))
        self.label_19 = QLabel(self.CH2)
        self.label_19.setObjectName(u"label_19")
        self.label_19.setGeometry(QRect(10, 190, 131, 16))
        self.inject_time_ch2 = QLabel(self.CH2)
        self.inject_time_ch2.setObjectName(u"inject_time_ch2")
        self.inject_time_ch2.setGeometry(QRect(150, 190, 71, 16))
        self.label_20 = QLabel(self.CH2)
        self.label_20.setObjectName(u"label_20")
        self.label_20.setGeometry(QRect(230, 190, 16, 16))
        self.label_20.setMinimumSize(QSize(10, 10))
        self.run_rate_ch2 = QComboBox(self.CH2)
        self.run_rate_ch2.addItem("")
        self.run_rate_ch2.addItem("")
        self.run_rate_ch2.addItem("")
        self.run_rate_ch2.addItem("")
        self.run_rate_ch2.setObjectName(u"run_rate_ch2")
        self.run_rate_ch2.setGeometry(QRect(110, 50, 71, 25))
        self.run_rate_ch2.setMinimumSize(QSize(40, 25))
        self.sync_2 = QCheckBox(self.CH2)
        self.sync_2.setObjectName(u"sync_2")
        self.sync_2.setEnabled(True)
        self.sync_2.setGeometry(QRect(170, 10, 81, 41))
        self.pump_flow_ch2 = QGroupBox(self.CH2)
        self.pump_flow_ch2.setObjectName(u"pump_flow_ch2")
        self.pump_flow_ch2.setGeometry(QRect(10, 120, 115, 65))
        self.spr_ch2 = QRadioButton(self.pump_flow_ch2)
        self.spr_ch2.setObjectName(u"spr_ch2")
        self.spr_ch2.setGeometry(QRect(30, 40, 81, 20))
        self.waste_ch2 = QRadioButton(self.pump_flow_ch2)
        self.waste_ch2.setObjectName(u"waste_ch2")
        self.waste_ch2.setGeometry(QRect(30, 20, 81, 20))
        self.waste_ch2.setChecked(True)
        self.sample_flow_ch2 = QGroupBox(self.CH2)
        self.sample_flow_ch2.setObjectName(u"sample_flow_ch2")
        self.sample_flow_ch2.setEnabled(True)
        self.sample_flow_ch2.setGeometry(QRect(130, 120, 115, 65))
        self.inject_ch2 = QRadioButton(self.sample_flow_ch2)
        self.inject_ch2.setObjectName(u"inject_ch2")
        self.inject_ch2.setGeometry(QRect(30, 40, 71, 20))
        self.load_ch2 = QRadioButton(self.sample_flow_ch2)
        self.load_ch2.setObjectName(u"load_ch2")
        self.load_ch2.setGeometry(QRect(30, 20, 71, 20))
        self.load_ch2.setChecked(True)
        self.sensor_frame_ch2 = QFrame(self.CH2)
        self.sensor_frame_ch2.setObjectName(u"sensor_frame_ch2")
        self.sensor_frame_ch2.setGeometry(QRect(100, 70, 151, 51))
        self.sensor_frame_ch2.setFrameShape(QFrame.StyledPanel)
        self.sensor_frame_ch2.setFrameShadow(QFrame.Raised)
        self.label_4 = QLabel(self.sensor_frame_ch2)
        self.label_4.setObjectName(u"label_4")
        self.label_4.setGeometry(QRect(10, 10, 31, 16))
        self.label_4.setMinimumSize(QSize(10, 10))
        self.flow2 = QLabel(self.sensor_frame_ch2)
        self.flow2.setObjectName(u"flow2")
        self.flow2.setGeometry(QRect(50, 10, 41, 16))
        self.label_9 = QLabel(self.sensor_frame_ch2)
        self.label_9.setObjectName(u"label_9")
        self.label_9.setGeometry(QRect(10, 30, 51, 16))
        self.temp2 = QLabel(self.sensor_frame_ch2)
        self.temp2.setObjectName(u"temp2")
        self.temp2.setGeometry(QRect(60, 30, 31, 16))
        self.label_7 = QLabel(self.sensor_frame_ch2)
        self.label_7.setObjectName(u"label_7")
        self.label_7.setGeometry(QRect(100, 10, 50, 16))
        self.label_7.setMinimumSize(QSize(50, 16))
        self.label_7.setMaximumSize(QSize(50, 16))
        self.label_7.setPixmap(QPixmap(u":/img/img/micro_per_min.png"))
        self.label_7.setScaledContents(True)
        self.label_12 = QLabel(self.sensor_frame_ch2)
        self.label_12.setObjectName(u"label_12")
        self.label_12.setGeometry(QRect(100, 30, 30, 16))
        self.label_12.setMinimumSize(QSize(30, 16))
        self.label_12.setMaximumSize(QSize(30, 16))
        self.label_12.setPixmap(QPixmap(u":/img/img/deg_c.png"))
        self.label_12.setScaledContents(True)
        self.label_6 = QLabel(self.CH2)
        self.label_6.setObjectName(u"label_6")
        self.label_6.setGeometry(QRect(190, 55, 50, 16))
        self.label_6.setMinimumSize(QSize(50, 16))
        self.label_6.setMaximumSize(QSize(50, 16))
        self.label_6.setPixmap(QPixmap(u":/img/img/micro_per_min.png"))
        self.label_6.setScaledContents(True)

        self.verticalLayout_2.addWidget(self.CH2, 0, Qt.AlignHCenter)


        self.gridLayout.addLayout(self.verticalLayout_2, 2, 0, 1, 1)


        self.retranslateUi(Kinetic)

        QMetaObject.connectSlotsByName(Kinetic)
    # setupUi

    def retranslateUi(self, Kinetic):
        Kinetic.setWindowTitle(QCoreApplication.translate("Kinetic", u"Form", None))
        self.CH1.setTitle(QCoreApplication.translate("Kinetic", u"Kinetic Channel 1", None))
        self.run1.setText(QCoreApplication.translate("Kinetic", u"Run", None))
        self.flush1.setText(QCoreApplication.translate("Kinetic", u"Flush", None))
        self.run_rate_ch1.setItemText(0, QCoreApplication.translate("Kinetic", u"25", None))
        self.run_rate_ch1.setItemText(1, QCoreApplication.translate("Kinetic", u"50", None))
        self.run_rate_ch1.setItemText(2, QCoreApplication.translate("Kinetic", u"100", None))
        self.run_rate_ch1.setItemText(3, QCoreApplication.translate("Kinetic", u"200", None))

        self.label.setText("")
        self.status1.setText(QCoreApplication.translate("Kinetic", u"<status>", None))
        self.label_15.setText(QCoreApplication.translate("Kinetic", u"Status:", None))
        self.label_17.setText(QCoreApplication.translate("Kinetic", u"Sample Injection Time:", None))
        self.inject_time_ch1.setText("")
        self.label_18.setText(QCoreApplication.translate("Kinetic", u"<html><head/><body><p>s</p></body></html>", None))
        self.sync_1.setText(QCoreApplication.translate("Kinetic", u"Sync\n"
"Channels", None))
        self.pump_flow_ch1.setTitle(QCoreApplication.translate("Kinetic", u"Buffer Flow ", None))
        self.spr_ch1.setText(QCoreApplication.translate("Kinetic", u"Channel B", None))
        self.waste_ch1.setText(QCoreApplication.translate("Kinetic", u"Channel A", None))
        self.sample_flow_ch1.setTitle(QCoreApplication.translate("Kinetic", u"Sample Loop", None))
        self.inject_ch1.setText(QCoreApplication.translate("Kinetic", u"Inject", None))
        self.load_ch1.setText(QCoreApplication.translate("Kinetic", u"Load", None))
        self.label_5.setText("")
        self.label_2.setText(QCoreApplication.translate("Kinetic", u"Flow:", None))
        self.flow1.setText(QCoreApplication.translate("Kinetic", u"###.#", None))
        self.label_3.setText(QCoreApplication.translate("Kinetic", u"Temp:", None))
        self.temp1.setText(QCoreApplication.translate("Kinetic", u"##.#", None))
        self.label_11.setText("")
        self.CH2.setTitle(QCoreApplication.translate("Kinetic", u"Kinetic Channel 2", None))
        self.run2.setText(QCoreApplication.translate("Kinetic", u"Run", None))
        self.flush2.setText(QCoreApplication.translate("Kinetic", u"Flush", None))
        self.label_16.setText(QCoreApplication.translate("Kinetic", u"Status:", None))
        self.status2.setText(QCoreApplication.translate("Kinetic", u"<status>", None))
        self.label_19.setText(QCoreApplication.translate("Kinetic", u"Sample Injection Time:", None))
        self.inject_time_ch2.setText("")
        self.label_20.setText(QCoreApplication.translate("Kinetic", u"<html><head/><body><p>s</p></body></html>", None))
        self.run_rate_ch2.setItemText(0, QCoreApplication.translate("Kinetic", u"25", None))
        self.run_rate_ch2.setItemText(1, QCoreApplication.translate("Kinetic", u"50", None))
        self.run_rate_ch2.setItemText(2, QCoreApplication.translate("Kinetic", u"100", None))
        self.run_rate_ch2.setItemText(3, QCoreApplication.translate("Kinetic", u"200", None))

        self.sync_2.setText(QCoreApplication.translate("Kinetic", u"Sync\n"
"Channels", None))
        self.pump_flow_ch2.setTitle(QCoreApplication.translate("Kinetic", u"Buffer Flow", None))
        self.spr_ch2.setText(QCoreApplication.translate("Kinetic", u"Channel D", None))
        self.waste_ch2.setText(QCoreApplication.translate("Kinetic", u"Channel C", None))
        self.sample_flow_ch2.setTitle(QCoreApplication.translate("Kinetic", u"Sample Loop", None))
        self.inject_ch2.setText(QCoreApplication.translate("Kinetic", u"Inject", None))
        self.load_ch2.setText(QCoreApplication.translate("Kinetic", u"Load", None))
        self.label_4.setText(QCoreApplication.translate("Kinetic", u"Flow:", None))
        self.flow2.setText(QCoreApplication.translate("Kinetic", u"###.#", None))
        self.label_9.setText(QCoreApplication.translate("Kinetic", u"Temp:", None))
        self.temp2.setText(QCoreApplication.translate("Kinetic", u"##.#", None))
        self.label_7.setText("")
        self.label_12.setText("")
        self.label_6.setText("")
    # retranslateUi

