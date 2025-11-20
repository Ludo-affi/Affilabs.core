# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'main.ui'
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
from PySide6.QtWidgets import (QApplication, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy, QSpacerItem,
    QVBoxLayout, QWidget)
import ui.ai_rc

class Ui_mainWindow(object):
    def setupUi(self, mainWindow):
        if not mainWindow.objectName():
            mainWindow.setObjectName(u"mainWindow")
        mainWindow.resize(1400, 800)  # Professional default size
        mainWindow.setMinimumSize(QSize(1200, 700))
        font = QFont()
        font.setFamilies([u"Segoe UI"])
        mainWindow.setFont(font)
        icon = QIcon()
        icon.addFile(u":/img/img/affinite2.ico", QSize(), QIcon.Normal, QIcon.Off)
        mainWindow.setWindowIcon(icon)
        mainWindow.setStyleSheet(u"")
        self.gridLayout_2 = QGridLayout(mainWindow)
        self.gridLayout_2.setSpacing(0)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gridLayout_2.setContentsMargins(0, 0, 0, 0)
        self.main_frame = QFrame(mainWindow)
        self.main_frame.setObjectName(u"main_frame")
        palette = QPalette()
        brush = QBrush(QColor(218, 228, 238, 255))
        brush.setStyle(Qt.SolidPattern)
        palette.setBrush(QPalette.Active, QPalette.Button, brush)
        brush1 = QBrush(QColor(255, 255, 255, 255))
        brush1.setStyle(Qt.SolidPattern)
        palette.setBrush(QPalette.Active, QPalette.Base, brush1)
        brush2 = QBrush(QColor(254, 254, 254, 255))
        brush2.setStyle(Qt.SolidPattern)
        palette.setBrush(QPalette.Active, QPalette.Window, brush2)
        palette.setBrush(QPalette.Inactive, QPalette.Button, brush)
        palette.setBrush(QPalette.Inactive, QPalette.Base, brush1)
        palette.setBrush(QPalette.Inactive, QPalette.Window, brush2)
        palette.setBrush(QPalette.Disabled, QPalette.Button, brush)
        palette.setBrush(QPalette.Disabled, QPalette.Base, brush2)
        palette.setBrush(QPalette.Disabled, QPalette.Window, brush2)
        self.main_frame.setPalette(palette)
        self.main_frame.setStyleSheet(u"")
        self.main_frame.setFrameShape(QFrame.NoFrame)
        self.main_frame.setFrameShadow(QFrame.Sunken)
        self.main_frame.setLineWidth(0)
        self.verticalLayout = QVBoxLayout(self.main_frame)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.tool_bar = QFrame(self.main_frame)
        self.tool_bar.setObjectName(u"tool_bar")
        self.tool_bar.setMinimumSize(QSize(0, 60))
        self.tool_bar.setMaximumSize(QSize(16777215, 60))
        font1 = QFont()
        font1.setFamilies([u"Segoe UI"])
        font1.setPointSize(8)
        self.tool_bar.setFont(font1)
        self.tool_bar.setStyleSheet(u"")
        self.tool_bar.setFrameShape(QFrame.NoFrame)
        self.tool_bar.setFrameShadow(QFrame.Plain)
        self.tool_bar.setLineWidth(0)
        self.horizontalLayout = QHBoxLayout(self.tool_bar)
        self.horizontalLayout.setSpacing(2)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(5, 0, 5, 0)
        self.label = QLabel(self.tool_bar)
        self.label.setObjectName(u"label")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(self.label.sizePolicy().hasHeightForWidth())
        self.label.setSizePolicy(sizePolicy)
        self.label.setMinimumSize(QSize(100, 60))
        self.label.setMaximumSize(QSize(150, 60))
        self.label.setFrameShape(QFrame.NoFrame)
        self.label.setFrameShadow(QFrame.Raised)
        self.label.setPixmap(QPixmap(u":/img/img/affinite-no-background.png"))
        self.label.setScaledContents(True)
        self.label.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignTop)
        self.label.setMargin(0)

        self.horizontalLayout.addWidget(self.label)

        self.frame_2 = QFrame(self.tool_bar)
        self.frame_2.setObjectName(u"frame_2")
        self.frame_2.setMinimumSize(QSize(500, 40))
        self.frame_2.setMaximumSize(QSize(600, 60))
        self.frame_2.setFrameShape(QFrame.StyledPanel)
        self.frame_2.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_4 = QHBoxLayout(self.frame_2)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(140, 0, 0, 0)  # Left margin to align with main page
        self.sensorgram_btn = QPushButton(self.frame_2)
        self.sensorgram_btn.setObjectName(u"sensorgram_btn")
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.sensorgram_btn.sizePolicy().hasHeightForWidth())
        self.sensorgram_btn.setSizePolicy(sizePolicy1)
        self.sensorgram_btn.setMinimumSize(QSize(90, 35))
        self.sensorgram_btn.setMaximumSize(QSize(110, 16777215))
        font2 = QFont()
        font2.setFamilies([u"Segoe UI"])
        font2.setPointSize(9)
        self.sensorgram_btn.setFont(font2)
        self.sensorgram_btn.setLayoutDirection(Qt.LeftToRight)
        self.sensorgram_btn.setAutoFillBackground(False)
        self.sensorgram_btn.setStyleSheet(u"QPushButton {\n"
"\n"
"	background-color: rgb(240, 240, 240); \n"
"	border: 1px solid; \n"
"	border-radius: 3px;\n"
"\n"
"}\n"
"\n"
"QPushButton::hover{\n"
"	background: rgb(253, 253, 253);\n"
"	border: 1px raised;\n"
"	border-radius: 5px;\n"
"}")
        self.sensorgram_btn.setAutoRepeat(False)
        self.sensorgram_btn.setAutoExclusive(False)
        self.sensorgram_btn.setAutoDefault(False)
        self.sensorgram_btn.setFlat(False)

        self.horizontalLayout_4.addWidget(self.sensorgram_btn)

        self.spectroscopy_btn = QPushButton(self.frame_2)
        self.spectroscopy_btn.setObjectName(u"spectroscopy_btn")
        sizePolicy1.setHeightForWidth(self.spectroscopy_btn.sizePolicy().hasHeightForWidth())
        self.spectroscopy_btn.setSizePolicy(sizePolicy1)
        self.spectroscopy_btn.setMinimumSize(QSize(102, 35))
        self.spectroscopy_btn.setMaximumSize(QSize(110, 16777215))
        self.spectroscopy_btn.setFont(font2)
        self.spectroscopy_btn.setLayoutDirection(Qt.LeftToRight)
        self.spectroscopy_btn.setAutoFillBackground(False)
        self.spectroscopy_btn.setStyleSheet(u"QPushButton {\n"
"\n"
"	background-color: rgb(240, 240, 240); \n"
"	border: 1px solid; \n"
"	border-radius: 3px;\n"
"\n"
"}\n"
"\n"
"QPushButton::hover{\n"
"	background: rgb(253, 253, 253);\n"
"	border: 1px raised;\n"
"	border-radius: 5px;\n"
"}")
        self.spectroscopy_btn.setAutoRepeat(False)
        self.spectroscopy_btn.setAutoExclusive(False)
        self.spectroscopy_btn.setAutoDefault(False)
        self.spectroscopy_btn.setFlat(False)

        self.horizontalLayout_4.addWidget(self.spectroscopy_btn)

        self.data_processing_btn = QPushButton(self.frame_2)
        self.data_processing_btn.setObjectName(u"data_processing_btn")
        sizePolicy1.setHeightForWidth(self.data_processing_btn.sizePolicy().hasHeightForWidth())
        self.data_processing_btn.setSizePolicy(sizePolicy1)
        self.data_processing_btn.setMinimumSize(QSize(125, 35))
        self.data_processing_btn.setMaximumSize(QSize(135, 16777215))
        self.data_processing_btn.setFont(font2)
        self.data_processing_btn.setLayoutDirection(Qt.LeftToRight)
        self.data_processing_btn.setAutoFillBackground(False)
        self.data_processing_btn.setStyleSheet(u"QPushButton {\n"
"\n"
"	background-color: rgb(240, 240, 240); \n"
"	border: 1px solid; \n"
"	border-radius: 3px;\n"
"\n"
"}\n"
"\n"
"QPushButton::hover{\n"
"	background: rgb(253, 253, 253);\n"
"	border: 1px raised;\n"
"	border-radius: 5px;\n"
"}")
        self.data_processing_btn.setAutoRepeat(False)
        self.data_processing_btn.setAutoExclusive(False)
        self.data_processing_btn.setAutoDefault(False)
        self.data_processing_btn.setFlat(False)

        self.horizontalLayout_4.addWidget(self.data_processing_btn)

        self.data_analysis_btn = QPushButton(self.frame_2)
        self.data_analysis_btn.setObjectName(u"data_analysis_btn")
        self.data_analysis_btn.setEnabled(True)
        sizePolicy1.setHeightForWidth(self.data_analysis_btn.sizePolicy().hasHeightForWidth())
        self.data_analysis_btn.setSizePolicy(sizePolicy1)
        self.data_analysis_btn.setMinimumSize(QSize(118, 35))
        self.data_analysis_btn.setMaximumSize(QSize(135, 16777215))
        self.data_analysis_btn.setFont(font2)
        self.data_analysis_btn.setLayoutDirection(Qt.LeftToRight)
        self.data_analysis_btn.setAutoFillBackground(False)
        self.data_analysis_btn.setStyleSheet(u"QPushButton {\n"
"\n"
"	background-color: rgb(240, 240, 240);  \n"
"	border: 1px solid rgb(127, 127, 127);\n"
"	border-radius: 3px;\n"
"\n"
"}\n"
"\n"
"QPushButton::hover{\n"
"	background: rgb(253, 253, 253);\n"
"	border: 1px raised;\n"
"	border-radius: 5px;\n"
"}")
        self.data_analysis_btn.setAutoRepeat(False)
        self.data_analysis_btn.setAutoExclusive(False)
        self.data_analysis_btn.setAutoDefault(False)
        self.data_analysis_btn.setFlat(False)

        self.horizontalLayout_4.addWidget(self.data_analysis_btn)


        self.horizontalLayout.addWidget(self.frame_2)

        self.horizontalSpacer_3 = QSpacerItem(10, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer_3)

        self.adv_btn = QPushButton(self.tool_bar)
        self.adv_btn.setObjectName(u"adv_btn")
        self.adv_btn.setEnabled(False)
        sizePolicy2 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.adv_btn.sizePolicy().hasHeightForWidth())
        self.adv_btn.setSizePolicy(sizePolicy2)
        self.adv_btn.setMinimumSize(QSize(35, 35))
        self.adv_btn.setMaximumSize(QSize(35, 35))
        font3 = QFont()
        font3.setFamilies([u"Segoe UI"])
        font3.setPointSize(5)
        self.adv_btn.setFont(font3)
        self.adv_btn.setMouseTracking(True)
        self.adv_btn.setLayoutDirection(Qt.LeftToRight)
        self.adv_btn.setAutoFillBackground(False)
        self.adv_btn.setStyleSheet(u"QPushButton{\n"
"	border: none;\n"
"	background: none;\n"
"}\n"
"\n"
"QPushButton::hover{\n"
"	background: white;\n"
"	border: 1px raised;\n"
"	border-radius: 8px;\n"
"}")
        icon1 = QIcon()
        icon1.addFile(u":/img/img/settings.png", QSize(), QIcon.Normal, QIcon.Off)
        self.adv_btn.setIcon(icon1)
        self.adv_btn.setIconSize(QSize(28, 28))
        self.adv_btn.setAutoRepeat(False)
        self.adv_btn.setAutoExclusive(False)
        self.adv_btn.setAutoDefault(False)
        self.adv_btn.setFlat(False)

        self.horizontalLayout.addWidget(self.adv_btn, 0, Qt.AlignHCenter|Qt.AlignVCenter)

        self.rec_btn = QPushButton(self.tool_bar)
        self.rec_btn.setObjectName(u"rec_btn")
        sizePolicy2.setHeightForWidth(self.rec_btn.sizePolicy().hasHeightForWidth())
        self.rec_btn.setSizePolicy(sizePolicy2)
        self.rec_btn.setMinimumSize(QSize(37, 35))
        self.rec_btn.setMaximumSize(QSize(37, 35))
        self.rec_btn.setFont(font3)
        self.rec_btn.setMouseTracking(True)
        self.rec_btn.setLayoutDirection(Qt.LeftToRight)
        self.rec_btn.setAutoFillBackground(False)
        self.rec_btn.setStyleSheet(u"QPushButton{\n"
"	border: none;\n"
"	background: none;\n"
"	margin: 0px;\n"
"}\n"
"\n"
"QPushButton::hover{\n"
"	background: white;\n"
"	border: 1px raised;\n"
"	border-radius: 8px;\n"
"}")
        icon2 = QIcon()
        icon2.addFile(u":/img/img/record.png", QSize(), QIcon.Normal, QIcon.Off)
        self.rec_btn.setIcon(icon2)
        self.rec_btn.setIconSize(QSize(23, 23))
        self.rec_btn.setAutoRepeat(False)
        self.rec_btn.setAutoExclusive(False)
        self.rec_btn.setAutoDefault(False)
        self.rec_btn.setFlat(False)

        self.horizontalLayout.addWidget(self.rec_btn, 0, Qt.AlignHCenter|Qt.AlignVCenter)

        self.recording_status = QLabel(self.tool_bar)
        self.recording_status.setObjectName(u"recording_status")
        sizePolicy3 = QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.recording_status.sizePolicy().hasHeightForWidth())
        self.recording_status.setSizePolicy(sizePolicy3)
        self.recording_status.setMinimumSize(QSize(85, 40))
        self.recording_status.setMaximumSize(QSize(85, 16777215))
        font4 = QFont()
        font4.setFamilies([u"Segoe UI Black"])
        font4.setPointSize(8)
        font4.setItalic(False)
        self.recording_status.setFont(font4)
        self.recording_status.setAutoFillBackground(False)
        self.recording_status.setStyleSheet(u"background:none;\n"
"color: red;\n"
"font: 87 8pt \"Segoe UI Black\";\n"
"\n"
"\n"
"\n"
"")
        self.recording_status.setAlignment(Qt.AlignCenter)

        self.horizontalLayout.addWidget(self.recording_status)

        self.power_btn = QPushButton(self.tool_bar)
        self.power_btn.setObjectName(u"power_btn")
        self.power_btn.setMinimumSize(QSize(90, 90))
        self.power_btn.setMaximumSize(QSize(90, 90))
        font_power = QFont()
        font_power.setFamilies([u"Segoe UI"])
        font_power.setPointSize(48)
        font_power.setBold(False)
        self.power_btn.setFont(font_power)
        self.power_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.power_btn.setToolTip(u"OFF")
        self.power_btn.setStyleSheet(u"QPushButton {\n"
"    background-color: transparent;\n"
"    color: rgb(150, 150, 150);\n"
"    border: none;\n"
"}\n"
"\n"
"QPushButton:hover {\n"
"    color: rgb(100, 100, 100);\n"
"}\n"
"\n"
"QPushButton:pressed {\n"
"    color: rgb(50, 50, 50);\n"
"}")
        self.power_btn.setText(u"⏻")

        self.horizontalLayout.addWidget(self.power_btn, 0, Qt.AlignHCenter|Qt.AlignVCenter)

        self.horizontalSpacer_2 = QSpacerItem(90, 20, QSizePolicy.Preferred, QSizePolicy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer_2)


        self.verticalLayout.addWidget(self.tool_bar)

        self.main_display = QFrame(self.main_frame)
        self.main_display.setObjectName(u"main_display")
        self.main_display.setFont(font2)
        self.main_display.setStyleSheet(u"QFrame#main_display {\n"
"    background-color: rgb(240, 240, 240);\n"
"    border: none;\n"
"}")
        self.main_display.setFrameShape(QFrame.NoFrame)
        self.main_display.setFrameShadow(QFrame.Raised)
        self.main_display.setLineWidth(0)
        self.main_display.setContentsMargins(30, 20, 30, 30)

        self.verticalLayout.addWidget(self.main_display)

        self.statusBar = QWidget(self.main_frame)
        self.statusBar.setObjectName(u"statusBar")
        sizePolicy1.setHeightForWidth(self.statusBar.sizePolicy().hasHeightForWidth())
        self.statusBar.setSizePolicy(sizePolicy1)
        font5 = QFont()
        font5.setFamilies([u"Segoe UI"])
        font5.setPointSize(10)
        font5.setBold(False)
        self.statusBar.setFont(font5)
        self.statusBar.setStyleSheet(u"")
        self.layout_statusbar = QHBoxLayout(self.statusBar)
        self.layout_statusbar.setSpacing(5)
        self.layout_statusbar.setObjectName(u"layout_statusbar")
        self.layout_statusbar.setContentsMargins(0, 0, 5, 0)
        self.frame = QFrame(self.statusBar)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_2 = QHBoxLayout(self.frame)
        self.horizontalLayout_2.setSpacing(0)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(2, 3, 2, 3)
        self.device = QLabel(self.frame)
        self.device.setObjectName(u"device")
        font6 = QFont()
        font6.setFamilies([u"Segoe UI"])
        font6.setPointSize(11)
        font6.setBold(True)
        self.device.setFont(font6)
        self.device.setStyleSheet(u"QLabel#device{\n"
"\n"
"	background-color: rgb(46, 48, 227);\n"
"	color: 'white';\n"
"	border-radius: 3px;\n"
"\n"
"}")
        self.device.setAlignment(Qt.AlignCenter)
        self.device.setMargin(1)
        self.device.setIndent(0)

        self.horizontalLayout_2.addWidget(self.device)


        self.layout_statusbar.addWidget(self.frame)

        self.status = QLabel(self.statusBar)
        self.status.setObjectName(u"status")
        self.status.setFont(font6)
        self.status.setMargin(0)
        self.status.setIndent(0)

        self.layout_statusbar.addWidget(self.status)

        self.horizontalSpacer = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.layout_statusbar.addItem(self.horizontalSpacer)

        self.version = QLabel(self.statusBar)
        self.version.setObjectName(u"version")
        font7 = QFont()
        font7.setFamilies([u"Segoe UI"])
        font7.setPointSize(9)
        font7.setBold(False)
        self.version.setFont(font7)
        self.version.setAlignment(Qt.AlignCenter)

        self.layout_statusbar.addWidget(self.version, 0, Qt.AlignHCenter)

        self.horizontalSpacer_4 = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.layout_statusbar.addItem(self.horizontalSpacer_4)

        # Ensure statusBar is visible
        self.statusBar.setVisible(True)
        self.statusBar.setMinimumHeight(25)

        self.verticalLayout.addWidget(self.statusBar)


        self.gridLayout_2.addWidget(self.main_frame, 0, 0, 1, 1)


        self.retranslateUi(mainWindow)

        self.sensorgram_btn.setDefault(False)
        self.spectroscopy_btn.setDefault(False)
        self.data_processing_btn.setDefault(False)
        self.data_analysis_btn.setDefault(False)
        self.adv_btn.setDefault(False)
        self.rec_btn.setDefault(False)


        QMetaObject.connectSlotsByName(mainWindow)
    # setupUi

    def retranslateUi(self, mainWindow):
        mainWindow.setWindowTitle(QCoreApplication.translate("mainWindow", u"ezControl Software", None))
        self.label.setText("")
        self.sensorgram_btn.setText(QCoreApplication.translate("mainWindow", u"Sensorgram", None))
        self.spectroscopy_btn.setText(QCoreApplication.translate("mainWindow", u"Spectroscopy", None))
        self.data_processing_btn.setText(QCoreApplication.translate("mainWindow", u"Processing", None))
        self.data_analysis_btn.setText(QCoreApplication.translate("mainWindow", u"Analysis", None))
#if QT_CONFIG(tooltip)
        self.adv_btn.setToolTip(QCoreApplication.translate("mainWindow", u"Advanced Settings", None))
#endif // QT_CONFIG(tooltip)
        self.adv_btn.setText("")
#if QT_CONFIG(tooltip)
        self.rec_btn.setToolTip(QCoreApplication.translate("mainWindow", u"Start/Stop\n"
"Recording", None))
#endif // QT_CONFIG(tooltip)
        self.rec_btn.setText("")
        self.recording_status.setText(QCoreApplication.translate("mainWindow", u"NOT\n"
"RECORDING", None))
        self.device.setText(QCoreApplication.translate("mainWindow", u"No Devices", None))
        self.status.setText(QCoreApplication.translate("mainWindow", u"Status", None))
        self.version.setText(QCoreApplication.translate("mainWindow", u"Version", None))
    # retranslateUi

