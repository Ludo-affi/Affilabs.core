################################################################################
## Form generated from reading UI file 'main.ui'
##
## Created by: Qt User Interface Compiler version 6.6.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import QCoreApplication, QMetaObject, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPalette, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)


class Ui_mainWindow:
    def setupUi(self, mainWindow):
        if not mainWindow.objectName():
            mainWindow.setObjectName("mainWindow")
        mainWindow.resize(1200, 700)
        mainWindow.setMinimumSize(QSize(1200, 700))
        font = QFont()
        font.setFamilies(["Segoe UI"])
        mainWindow.setFont(font)
        icon = QIcon()
        icon.addFile(":/img/img/affinite2.ico", QSize(), QIcon.Normal, QIcon.Off)
        mainWindow.setWindowIcon(icon)
        mainWindow.setStyleSheet("")
        self.gridLayout_2 = QGridLayout(mainWindow)
        self.gridLayout_2.setSpacing(0)
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.gridLayout_2.setContentsMargins(0, 0, 0, 0)
        self.main_frame = QFrame(mainWindow)
        self.main_frame.setObjectName("main_frame")
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
        self.main_frame.setStyleSheet("")
        self.main_frame.setFrameShape(QFrame.NoFrame)
        self.main_frame.setFrameShadow(QFrame.Sunken)
        self.main_frame.setLineWidth(0)
        self.verticalLayout = QVBoxLayout(self.main_frame)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName("verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.tool_bar = QFrame(self.main_frame)
        self.tool_bar.setObjectName("tool_bar")
        self.tool_bar.setMaximumSize(QSize(16777215, 80))
        font1 = QFont()
        font1.setFamilies(["Segoe UI"])
        font1.setPointSize(8)
        self.tool_bar.setFont(font1)
        self.tool_bar.setStyleSheet("")
        self.tool_bar.setFrameShape(QFrame.NoFrame)
        self.tool_bar.setFrameShadow(QFrame.Plain)
        self.tool_bar.setLineWidth(0)
        self.horizontalLayout = QHBoxLayout(self.tool_bar)
        self.horizontalLayout.setSpacing(2)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.horizontalLayout.setContentsMargins(5, 0, 5, 0)
        self.label = QLabel(self.tool_bar)
        self.label.setObjectName("label")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(self.label.sizePolicy().hasHeightForWidth())
        self.label.setSizePolicy(sizePolicy)
        self.label.setMinimumSize(QSize(100, 60))
        self.label.setMaximumSize(QSize(150, 60))
        self.label.setFrameShape(QFrame.NoFrame)
        self.label.setFrameShadow(QFrame.Raised)
        self.label.setPixmap(QPixmap(":/img/img/affinite-no-background.png"))
        self.label.setScaledContents(True)
        self.label.setAlignment(Qt.AlignLeading | Qt.AlignLeft | Qt.AlignTop)
        self.label.setMargin(0)

        self.horizontalLayout.addWidget(self.label)

        self.frame_2 = QFrame(self.tool_bar)
        self.frame_2.setObjectName("frame_2")
        self.frame_2.setMinimumSize(QSize(500, 40))
        self.frame_2.setMaximumSize(QSize(600, 60))
        self.frame_2.setFrameShape(QFrame.StyledPanel)
        self.frame_2.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_4 = QHBoxLayout(self.frame_2)
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        self.sensorgram_btn = QPushButton(self.frame_2)
        self.sensorgram_btn.setObjectName("sensorgram_btn")
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(
            self.sensorgram_btn.sizePolicy().hasHeightForWidth(),
        )
        self.sensorgram_btn.setSizePolicy(sizePolicy1)
        self.sensorgram_btn.setMinimumSize(QSize(90, 35))
        self.sensorgram_btn.setMaximumSize(QSize(110, 16777215))
        font2 = QFont()
        font2.setFamilies(["Segoe UI"])
        font2.setPointSize(9)
        self.sensorgram_btn.setFont(font2)
        self.sensorgram_btn.setLayoutDirection(Qt.LeftToRight)
        self.sensorgram_btn.setAutoFillBackground(False)
        self.sensorgram_btn.setStyleSheet(
            "QPushButton {\n"
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
            "}",
        )
        self.sensorgram_btn.setAutoRepeat(False)
        self.sensorgram_btn.setAutoExclusive(False)
        self.sensorgram_btn.setAutoDefault(False)
        self.sensorgram_btn.setFlat(False)

        self.horizontalLayout_4.addWidget(self.sensorgram_btn)



        self.data_processing_btn = QPushButton(self.frame_2)
        self.data_processing_btn.setObjectName("data_processing_btn")
        sizePolicy1.setHeightForWidth(
            self.data_processing_btn.sizePolicy().hasHeightForWidth(),
        )
        self.data_processing_btn.setSizePolicy(sizePolicy1)
        self.data_processing_btn.setMinimumSize(QSize(112, 35))
        self.data_processing_btn.setMaximumSize(QSize(120, 16777215))
        self.data_processing_btn.setFont(font2)
        self.data_processing_btn.setLayoutDirection(Qt.LeftToRight)
        self.data_processing_btn.setAutoFillBackground(False)
        self.data_processing_btn.setStyleSheet(
            "QPushButton {\n"
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
            "}",
        )
        self.data_processing_btn.setAutoRepeat(False)
        self.data_processing_btn.setAutoExclusive(False)
        self.data_processing_btn.setAutoDefault(False)
        self.data_processing_btn.setFlat(False)

        self.horizontalLayout_4.addWidget(self.data_processing_btn)

        self.data_analysis_btn = QPushButton(self.frame_2)
        self.data_analysis_btn.setObjectName("data_analysis_btn")
        self.data_analysis_btn.setEnabled(True)
        sizePolicy1.setHeightForWidth(
            self.data_analysis_btn.sizePolicy().hasHeightForWidth(),
        )
        self.data_analysis_btn.setSizePolicy(sizePolicy1)
        self.data_analysis_btn.setMinimumSize(QSize(100, 35))
        self.data_analysis_btn.setMaximumSize(QSize(110, 16777215))
        self.data_analysis_btn.setFont(font2)
        self.data_analysis_btn.setLayoutDirection(Qt.LeftToRight)
        self.data_analysis_btn.setAutoFillBackground(False)
        self.data_analysis_btn.setStyleSheet(
            "QPushButton {\n"
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
            "}",
        )
        self.data_analysis_btn.setAutoRepeat(False)
        self.data_analysis_btn.setAutoExclusive(False)
        self.data_analysis_btn.setAutoDefault(False)
        self.data_analysis_btn.setFlat(False)

        self.horizontalLayout_4.addWidget(self.data_analysis_btn)

        self.horizontalLayout.addWidget(self.frame_2)

        self.horizontalSpacer_3 = QSpacerItem(
            10,
            20,
            QSizePolicy.Expanding,
            QSizePolicy.Minimum,
        )

        self.horizontalLayout.addItem(self.horizontalSpacer_3)



        self.rec_btn = QPushButton(self.tool_bar)
        self.rec_btn.setObjectName("rec_btn")
        sizePolicy2.setHeightForWidth(self.rec_btn.sizePolicy().hasHeightForWidth())
        self.rec_btn.setSizePolicy(sizePolicy2)
        self.rec_btn.setMinimumSize(QSize(37, 35))
        self.rec_btn.setMaximumSize(QSize(37, 35))
        self.rec_btn.setFont(font3)
        self.rec_btn.setMouseTracking(True)
        self.rec_btn.setLayoutDirection(Qt.LeftToRight)
        self.rec_btn.setAutoFillBackground(False)
        self.rec_btn.setStyleSheet(
            "QPushButton{\n"
            "	border: none;\n"
            "	background: none;\n"
            "	margin: 0px;\n"
            "}\n"
            "\n"
            "QPushButton::hover{\n"
            "	background: white;\n"
            "	border: 1px raised;\n"
            "	border-radius: 8px;\n"
            "}",
        )
        icon2 = QIcon()
        icon2.addFile(":/img/img/record.png", QSize(), QIcon.Normal, QIcon.Off)
        self.rec_btn.setIcon(icon2)
        self.rec_btn.setIconSize(QSize(23, 23))
        self.rec_btn.setAutoRepeat(False)
        self.rec_btn.setAutoExclusive(False)
        self.rec_btn.setAutoDefault(False)
        self.rec_btn.setFlat(False)

        self.horizontalLayout.addWidget(
            self.rec_btn,
            0,
            Qt.AlignHCenter | Qt.AlignVCenter,
        )

        self.recording_status = QLabel(self.tool_bar)
        self.recording_status.setObjectName("recording_status")
        sizePolicy3 = QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(
            self.recording_status.sizePolicy().hasHeightForWidth(),
        )
        self.recording_status.setSizePolicy(sizePolicy3)
        self.recording_status.setMinimumSize(QSize(85, 40))
        self.recording_status.setMaximumSize(QSize(85, 16777215))
        font4 = QFont()
        font4.setFamilies(["Segoe UI Black"])
        font4.setPointSize(8)
        font4.setItalic(False)
        self.recording_status.setFont(font4)
        self.recording_status.setAutoFillBackground(False)
        self.recording_status.setStyleSheet(
            'background:none;\ncolor: red;\nfont: 87 8pt "Segoe UI Black";\n\n\n\n',
        )
        self.recording_status.setAlignment(Qt.AlignCenter)

        self.horizontalLayout.addWidget(self.recording_status)

        self.horizontalSpacer_2 = QSpacerItem(
            90,
            20,
            QSizePolicy.Preferred,
            QSizePolicy.Minimum,
        )

        self.horizontalLayout.addItem(self.horizontalSpacer_2)

        self.verticalLayout.addWidget(self.tool_bar)

        self.main_display = QFrame(self.main_frame)
        self.main_display.setObjectName("main_display")
        self.main_display.setFont(font2)
        self.main_display.setStyleSheet("")
        self.main_display.setFrameShape(QFrame.NoFrame)
        self.main_display.setFrameShadow(QFrame.Raised)
        self.main_display.setLineWidth(0)

        self.verticalLayout.addWidget(self.main_display)

        self.statusBar = QWidget(self.main_frame)
        self.statusBar.setObjectName("statusBar")
        sizePolicy1.setHeightForWidth(self.statusBar.sizePolicy().hasHeightForWidth())
        self.statusBar.setSizePolicy(sizePolicy1)
        font5 = QFont()
        font5.setFamilies(["Segoe UI"])
        font5.setPointSize(10)
        font5.setBold(False)
        self.statusBar.setFont(font5)
        self.statusBar.setStyleSheet("")
        self.layout_statusbar = QHBoxLayout(self.statusBar)
        self.layout_statusbar.setSpacing(5)
        self.layout_statusbar.setObjectName("layout_statusbar")
        self.layout_statusbar.setContentsMargins(0, 0, 5, 0)
        self.frame = QFrame(self.statusBar)
        self.frame.setObjectName("frame")
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_2 = QHBoxLayout(self.frame)
        self.horizontalLayout_2.setSpacing(0)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(2, 3, 2, 3)
        self.device = QLabel(self.frame)
        self.device.setObjectName("device")
        font6 = QFont()
        font6.setFamilies(["Segoe UI"])
        font6.setPointSize(11)
        font6.setBold(True)
        self.device.setFont(font6)
        self.device.setStyleSheet(
            "QLabel#device{\n"
            "\n"
            "	background-color: rgb(46, 48, 227);\n"
            "	color: 'white';\n"
            "	border-radius: 3px;\n"
            "\n"
            "}",
        )
        self.device.setAlignment(Qt.AlignCenter)
        self.device.setMargin(1)
        self.device.setIndent(0)

        self.horizontalLayout_2.addWidget(self.device)

        self.layout_statusbar.addWidget(self.frame)

        self.status = QLabel(self.statusBar)
        self.status.setObjectName("status")
        self.status.setFont(font6)
        self.status.setMargin(0)
        self.status.setIndent(0)

        self.layout_statusbar.addWidget(self.status)

        self.calibration_progress = QProgressBar(self.statusBar)
        self.calibration_progress.setObjectName("calibration_progress")
        self.calibration_progress.setMinimumSize(QSize(200, 20))
        self.calibration_progress.setMaximumSize(QSize(300, 25))
        self.calibration_progress.setVisible(False)  # Hidden by default
        self.calibration_progress.setStyleSheet(
            "QProgressBar {"
            "    border: 1px solid #ccc;"
            "    border-radius: 3px;"
            "    background-color: #f0f0f0;"
            "    text-align: center;"
            "    font-size: 10px;"
            "}"
            "QProgressBar::chunk {"
            "    background-color: #2e70e8;"
            "    border-radius: 2px;"
            "}",
        )

        self.layout_statusbar.addWidget(self.calibration_progress)

        self.horizontalSpacer = QSpacerItem(
            0,
            0,
            QSizePolicy.Expanding,
            QSizePolicy.Minimum,
        )

        self.layout_statusbar.addItem(self.horizontalSpacer)

        self.version = QLabel(self.statusBar)
        self.version.setObjectName("version")
        font7 = QFont()
        font7.setFamilies(["Segoe UI"])
        font7.setPointSize(9)
        font7.setBold(False)
        self.version.setFont(font7)
        self.version.setAlignment(Qt.AlignCenter)

        self.layout_statusbar.addWidget(self.version, 0, Qt.AlignHCenter)

        self.horizontalSpacer_4 = QSpacerItem(
            0,
            0,
            QSizePolicy.Expanding,
            QSizePolicy.Minimum,
        )

        self.layout_statusbar.addItem(self.horizontalSpacer_4)

        self.verticalLayout.addWidget(self.statusBar)

        self.gridLayout_2.addWidget(self.main_frame, 0, 0, 1, 1)

        self.retranslateUi(mainWindow)

        self.sensorgram_btn.setDefault(False)
        # self.spectroscopy_btn.setDefault(False)
        self.data_processing_btn.setDefault(False)
        self.data_analysis_btn.setDefault(False)
        # self.adv_btn.setDefault(False)
        self.rec_btn.setDefault(False)

        QMetaObject.connectSlotsByName(mainWindow)

    # setupUi

    def retranslateUi(self, mainWindow):
        mainWindow.setWindowTitle(
            QCoreApplication.translate("mainWindow", "ezControl Software", None),
        )
        self.label.setText("")
        self.sensorgram_btn.setText(
            QCoreApplication.translate("mainWindow", "Sensorgram", None),
        )
        self.data_processing_btn.setText(
            QCoreApplication.translate("mainWindow", "Data Processing", None),
        )
        self.data_analysis_btn.setText(
            QCoreApplication.translate("mainWindow", "Data Analysis", None),
        )
        # if QT_CONFIG(tooltip)
        # # endif // QT_CONFIG(tooltip)
        # if QT_CONFIG(tooltip)
        self.rec_btn.setToolTip(
            QCoreApplication.translate("mainWindow", "Start/Stop\nRecording", None),
        )
        # endif // QT_CONFIG(tooltip)
        self.rec_btn.setText("")
        self.recording_status.setText(
            QCoreApplication.translate("mainWindow", "NOT\nRECORDING", None),
        )
        self.device.setText(
            QCoreApplication.translate("mainWindow", "No Devices", None),
        )
        self.status.setText(QCoreApplication.translate("mainWindow", "Status", None))
        self.version.setText(QCoreApplication.translate("mainWindow", "Version", None))

    # retranslateUi
