# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'spectroscopy.ui'
##
## Created by: Qt User Interface Compiler version 6.10.0
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
    QGroupBox, QHBoxLayout, QLabel, QLayout,
    QPushButton, QRadioButton, QSizePolicy, QSpacerItem,
    QVBoxLayout, QWidget)

class Ui_Spectroscopy(object):
    def setupUi(self, Spectroscopy):
        if not Spectroscopy.objectName():
            Spectroscopy.setObjectName(u"Spectroscopy")
        Spectroscopy.resize(1229, 836)
        font = QFont()
        font.setFamilies([u"Segoe UI"])
        Spectroscopy.setFont(font)
        self.horizontalLayout = QHBoxLayout(Spectroscopy)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.Plots = QVBoxLayout()
        self.Plots.setSpacing(0)
        self.Plots.setObjectName(u"Plots")
        self.Plots.setSizeConstraint(QLayout.SetDefaultConstraint)
        self.Plots.setContentsMargins(2, 2, 2, 2)
        self.intensity_plot = QFrame(Spectroscopy)
        self.intensity_plot.setObjectName(u"intensity_plot")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.intensity_plot.sizePolicy().hasHeightForWidth())
        self.intensity_plot.setSizePolicy(sizePolicy)
        self.intensity_plot.setMinimumSize(QSize(710, 250))
        self.intensity_plot.setMaximumSize(QSize(10000, 10000))
        self.intensity_plot.setFrameShape(QFrame.StyledPanel)
        self.intensity_plot.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_2 = QHBoxLayout(self.intensity_plot)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalSpacer = QSpacerItem(959, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer)

        self.verticalSpacer_2 = QSpacerItem(20, 378, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.horizontalLayout_2.addItem(self.verticalSpacer_2)


        self.Plots.addWidget(self.intensity_plot)

        self.transmission_plot = QFrame(Spectroscopy)
        self.transmission_plot.setObjectName(u"transmission_plot")
        sizePolicy.setHeightForWidth(self.transmission_plot.sizePolicy().hasHeightForWidth())
        self.transmission_plot.setSizePolicy(sizePolicy)
        self.transmission_plot.setMinimumSize(QSize(710, 250))
        self.transmission_plot.setMaximumSize(QSize(10000, 10000))
        self.transmission_plot.setFrameShape(QFrame.StyledPanel)
        self.transmission_plot.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_3 = QHBoxLayout(self.transmission_plot)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalSpacer_2 = QSpacerItem(959, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_3.addItem(self.horizontalSpacer_2)

        self.verticalSpacer_3 = QSpacerItem(20, 378, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.horizontalLayout_3.addItem(self.verticalSpacer_3)


        self.Plots.addWidget(self.transmission_plot)


        self.horizontalLayout.addLayout(self.Plots)

        self.controls = QFrame(Spectroscopy)
        self.controls.setObjectName(u"controls")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.controls.sizePolicy().hasHeightForWidth())
        self.controls.setSizePolicy(sizePolicy1)
        self.controls.setMinimumSize(QSize(180, 0))
        self.controls.setMaximumSize(QSize(180, 16777215))
        font1 = QFont()
        font1.setFamilies([u"Segoe UI"])
        font1.setPointSize(11)
        self.controls.setFont(font1)
        self.controls.setFrameShape(QFrame.StyledPanel)
        self.controls.setFrameShadow(QFrame.Raised)
        self.verticalLayout_2 = QVBoxLayout(self.controls)
        self.verticalLayout_2.setSpacing(7)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.label_3 = QLabel(self.controls)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setMinimumSize(QSize(100, 0))
        font2 = QFont()
        font2.setFamilies([u"Segoe UI"])
        font2.setPointSize(11)
        font2.setBold(False)
        self.label_3.setFont(font2)
        self.label_3.setAlignment(Qt.AlignCenter)
        self.label_3.setMargin(0)

        self.verticalLayout_2.addWidget(self.label_3, 0, Qt.AlignHCenter)

        self.groupBox_2 = QGroupBox(self.controls)
        self.groupBox_2.setObjectName(u"groupBox_2")
        self.groupBox_2.setMinimumSize(QSize(100, 120))
        self.groupBox_2.setMaximumSize(QSize(100, 16777215))
        font3 = QFont()
        font3.setFamilies([u"Segoe UI"])
        font3.setPointSize(8)
        self.groupBox_2.setFont(font3)
        self.groupBox_2.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignVCenter)
        self.segment_A = QCheckBox(self.groupBox_2)
        self.segment_A.setObjectName(u"segment_A")
        self.segment_A.setGeometry(QRect(30, 30, 38, 16))
        font4 = QFont()
        font4.setFamilies([u"Segoe UI"])
        font4.setPointSize(9)
        font4.setBold(True)
        self.segment_A.setFont(font4)
        self.segment_A.setStyleSheet(u"QCheckBox{\n"
"	color: black;\n"
"	background: white;\n"
"	border: 1px solid rgb(171, 171, 171); \n"
"	border-radius: 3px;\n"
"}")
        self.segment_A.setChecked(True)
        self.segment_B = QCheckBox(self.groupBox_2)
        self.segment_B.setObjectName(u"segment_B")
        self.segment_B.setGeometry(QRect(30, 50, 38, 16))
        self.segment_B.setFont(font4)
        self.segment_B.setStyleSheet(u"QCheckBox{\n"
"	color: rgb(255, 0, 81);\n"
"	background: white;\n"
"	border: 1px solid rgb(171, 171, 171); \n"
"	border-radius: 3px;\n"
"}")
        self.segment_B.setChecked(True)
        self.segment_C = QCheckBox(self.groupBox_2)
        self.segment_C.setObjectName(u"segment_C")
        self.segment_C.setGeometry(QRect(30, 70, 38, 16))
        self.segment_C.setFont(font4)
        self.segment_C.setStyleSheet(u"QCheckBox{\n"
"	color: rgb(0, 174, 255);\n"
"	background:white;\n"
"	border: 1px solid rgb(171, 171, 171); \n"
"	border-radius: 3px;\n"
"}")
        self.segment_C.setChecked(True)
        self.segment_D = QCheckBox(self.groupBox_2)
        self.segment_D.setObjectName(u"segment_D")
        self.segment_D.setGeometry(QRect(30, 90, 38, 16))
        self.segment_D.setFont(font4)
        self.segment_D.setStyleSheet(u"QCheckBox{\n"
"	color: rgb(0, 230, 65);\n"
"	border: 1px solid rgb(171, 171, 171); \n"
"	background:white;\n"
"	border-radius: 3px;\n"
"}")
        self.segment_D.setChecked(True)

        self.verticalLayout_2.addWidget(self.groupBox_2, 0, Qt.AlignHCenter)

        self.verticalSpacer_4 = QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.verticalLayout_2.addItem(self.verticalSpacer_4)

        self.new_ref_btn = QPushButton(self.controls)
        self.new_ref_btn.setObjectName(u"new_ref_btn")
        self.new_ref_btn.setMinimumSize(QSize(100, 35))
        self.new_ref_btn.setMaximumSize(QSize(100, 40))
        font5 = QFont()
        font5.setFamilies([u"Segoe UI"])
        font5.setPointSize(8)
        font5.setBold(False)
        self.new_ref_btn.setFont(font5)
        self.new_ref_btn.setStyleSheet(u"QPushButton {\n"
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

        self.verticalLayout_2.addWidget(self.new_ref_btn, 0, Qt.AlignHCenter)

        self.verticalSpacer_6 = QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.verticalLayout_2.addItem(self.verticalSpacer_6)

        self.full_calibrate_btn = QPushButton(self.controls)
        self.full_calibrate_btn.setObjectName(u"full_calibrate_btn")
        self.full_calibrate_btn.setMinimumSize(QSize(100, 45))
        self.full_calibrate_btn.setMaximumSize(QSize(100, 50))
        self.full_calibrate_btn.setFont(font5)
        self.full_calibrate_btn.setStyleSheet(u"QPushButton {\n"
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

        self.verticalLayout_2.addWidget(self.full_calibrate_btn, 0, Qt.AlignHCenter)

        self.verticalSpacer_5 = QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.verticalLayout_2.addItem(self.verticalSpacer_5)

        self.prime_btn = QPushButton(self.controls)
        self.prime_btn.setObjectName(u"prime_btn")
        self.prime_btn.setMinimumSize(QSize(100, 35))
        self.prime_btn.setMaximumSize(QSize(100, 40))
        self.prime_btn.setFont(font3)
        self.prime_btn.setStyleSheet(u"QPushButton {\n"
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

        self.verticalLayout_2.addWidget(self.prime_btn, 0, Qt.AlignHCenter)

        self.verticalSpacer_7 = QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.verticalLayout_2.addItem(self.verticalSpacer_7)

        self.advanced = QGroupBox(self.controls)
        self.advanced.setObjectName(u"advanced")
        self.advanced.setMinimumSize(QSize(120, 250))
        self.advanced.setMaximumSize(QSize(120, 250))
        self.advanced.setFont(font3)
        self.advanced.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignTop)
        self.verticalLayout = QVBoxLayout(self.advanced)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 10)
        self.label = QLabel(self.advanced)
        self.label.setObjectName(u"label")
        self.label.setMaximumSize(QSize(16777215, 25))
        self.label.setFont(font3)
        self.label.setAlignment(Qt.AlignCenter)

        self.verticalLayout.addWidget(self.label)

        self.polarization = QComboBox(self.advanced)
        self.polarization.addItem("")
        self.polarization.addItem("")
        self.polarization.setObjectName(u"polarization")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.polarization.sizePolicy().hasHeightForWidth())
        self.polarization.setSizePolicy(sizePolicy2)
        self.polarization.setMinimumSize(QSize(75, 29))
        self.polarization.setMaximumSize(QSize(75, 30))
        font6 = QFont()
        font6.setFamilies([u"Segoe UI"])
        font6.setPointSize(10)
        self.polarization.setFont(font6)
        self.polarization.setStyleSheet(u"")
        self.polarization.setFrame(True)

        self.verticalLayout.addWidget(self.polarization, 0, Qt.AlignHCenter)

        self.label_2 = QLabel(self.advanced)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setMaximumSize(QSize(16777215, 25))
        self.label_2.setFont(font3)
        self.label_2.setAlignment(Qt.AlignCenter)

        self.verticalLayout.addWidget(self.label_2)

        self.led_mode = QComboBox(self.advanced)
        self.led_mode.addItem("")
        self.led_mode.addItem("")
        self.led_mode.setObjectName(u"led_mode")
        sizePolicy2.setHeightForWidth(self.led_mode.sizePolicy().hasHeightForWidth())
        self.led_mode.setSizePolicy(sizePolicy2)
        self.led_mode.setMinimumSize(QSize(75, 25))
        self.led_mode.setMaximumSize(QSize(25, 16777215))
        self.led_mode.setFont(font3)

        self.verticalLayout.addWidget(self.led_mode, 0, Qt.AlignHCenter)

        self.single_LED = QFrame(self.advanced)
        self.single_LED.setObjectName(u"single_LED")
        self.single_LED.setEnabled(False)
        self.single_LED.setMinimumSize(QSize(70, 100))
        self.single_LED.setMaximumSize(QSize(70, 100))
        self.single_LED.setFont(font3)
        self.verticalLayout_3 = QVBoxLayout(self.single_LED)
        self.verticalLayout_3.setSpacing(2)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(-1, 5, -1, 5)
        self.led_off = QRadioButton(self.single_LED)
        self.led_off.setObjectName(u"led_off")
        self.led_off.setChecked(True)

        self.verticalLayout_3.addWidget(self.led_off)

        self.single_A = QRadioButton(self.single_LED)
        self.single_A.setObjectName(u"single_A")

        self.verticalLayout_3.addWidget(self.single_A)

        self.single_B = QRadioButton(self.single_LED)
        self.single_B.setObjectName(u"single_B")

        self.verticalLayout_3.addWidget(self.single_B)

        self.single_C = QRadioButton(self.single_LED)
        self.single_C.setObjectName(u"single_C")

        self.verticalLayout_3.addWidget(self.single_C)

        self.single_D = QRadioButton(self.single_LED)
        self.single_D.setObjectName(u"single_D")

        self.verticalLayout_3.addWidget(self.single_D)


        self.verticalLayout.addWidget(self.single_LED, 0, Qt.AlignHCenter)


        self.verticalLayout_2.addWidget(self.advanced, 0, Qt.AlignHCenter)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_2.addItem(self.verticalSpacer)


        self.horizontalLayout.addWidget(self.controls)


        self.retranslateUi(Spectroscopy)

        QMetaObject.connectSlotsByName(Spectroscopy)
    # setupUi

    def retranslateUi(self, Spectroscopy):
        Spectroscopy.setWindowTitle(QCoreApplication.translate("Spectroscopy", u"Form", None))
        self.label_3.setText(QCoreApplication.translate("Spectroscopy", u"Spectroscopy", None))
        self.groupBox_2.setTitle(QCoreApplication.translate("Spectroscopy", u"Display ", None))
        self.segment_A.setText(QCoreApplication.translate("Spectroscopy", u"A", None))
        self.segment_B.setText(QCoreApplication.translate("Spectroscopy", u"B", None))
        self.segment_C.setText(QCoreApplication.translate("Spectroscopy", u"C", None))
        self.segment_D.setText(QCoreApplication.translate("Spectroscopy", u"D", None))
        self.new_ref_btn.setText(QCoreApplication.translate("Spectroscopy", u"New Reference", None))
        self.full_calibrate_btn.setText(QCoreApplication.translate("Spectroscopy", u"Auto-Align\n"
"&& Calibrate", None))
        self.prime_btn.setText(QCoreApplication.translate("Spectroscopy", u"Prime Pumps", None))
        self.advanced.setTitle(QCoreApplication.translate("Spectroscopy", u"Advanced ", None))
        self.label.setText(QCoreApplication.translate("Spectroscopy", u"Polarization:", None))
        self.polarization.setItemText(0, QCoreApplication.translate("Spectroscopy", u" P ", None))
        self.polarization.setItemText(1, QCoreApplication.translate("Spectroscopy", u" S ", None))

        self.label_2.setText(QCoreApplication.translate("Spectroscopy", u"LED Mode:", None))
        self.led_mode.setItemText(0, QCoreApplication.translate("Spectroscopy", u"Auto", None))
        self.led_mode.setItemText(1, QCoreApplication.translate("Spectroscopy", u"Single", None))

        self.led_off.setText(QCoreApplication.translate("Spectroscopy", u"Off", None))
        self.single_A.setText(QCoreApplication.translate("Spectroscopy", u"A", None))
        self.single_B.setText(QCoreApplication.translate("Spectroscopy", u"B", None))
        self.single_C.setText(QCoreApplication.translate("Spectroscopy", u"C", None))
        self.single_D.setText(QCoreApplication.translate("Spectroscopy", u"D", None))
    # retranslateUi

