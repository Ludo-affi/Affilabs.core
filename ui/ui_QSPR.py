################################################################################
## Form generated from reading UI file 'QSPR.ui'
##
## Created by: Qt User Interface Compiler version 6.6.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import QCoreApplication, QMetaObject, QRect, QSize, Qt
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)


class Ui_QSPR:
    def setupUi(self, QSPR):
        if not QSPR.objectName():
            QSPR.setObjectName("QSPR")
        QSPR.resize(260, 110)
        QSPR.setMinimumSize(QSize(260, 110))
        QSPR.setMaximumSize(QSize(260, 110))
        font = QFont()
        font.setFamilies(["Segoe UI"])
        QSPR.setFont(font)
        self.verticalLayout = QVBoxLayout(QSPR)
        self.verticalLayout.setObjectName("verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.QSPR_display = QGroupBox(QSPR)
        self.QSPR_display.setObjectName("QSPR_display")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.QSPR_display.sizePolicy().hasHeightForWidth())
        self.QSPR_display.setSizePolicy(sizePolicy)
        self.QSPR_display.setMinimumSize(QSize(260, 110))
        self.QSPR_display.setMaximumSize(QSize(260, 110))
        font1 = QFont()
        font1.setFamilies(["Segoe UI"])
        font1.setPointSize(9)
        font1.setBold(True)
        self.QSPR_display.setFont(font1)
        self.QSPR_display.setStyleSheet(
            "QGroupBox#QSPR_display::title{\n"
            "\n"
            "	margin: 0px 5px 0px 5px;\n"
            "	color: rgb(255, 255, 255);\n"
            "	background-color:rgb(46, 48, 227);\n"
            "	border-radius: 3px;\n"
            "\n"
            "}\n"
            "\n"
            "QGroupBox#QSPR_display{\n"
            "	\n"
            "	border: 2px solid rgba(46, 48, 227, 150);\n"
            "	border-radius: 3px;\n"
            "\n"
            "}"
        )
        self.shutdown_btn = QPushButton(self.QSPR_display)
        self.shutdown_btn.setObjectName("shutdown_btn")
        self.shutdown_btn.setGeometry(QRect(50, 25, 30, 30))
        sizePolicy1 = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(
            self.shutdown_btn.sizePolicy().hasHeightForWidth()
        )
        self.shutdown_btn.setSizePolicy(sizePolicy1)
        self.shutdown_btn.setMinimumSize(QSize(30, 30))
        self.shutdown_btn.setMaximumSize(QSize(30, 30))
        font2 = QFont()
        font2.setPointSize(5)
        self.shutdown_btn.setFont(font2)
        self.shutdown_btn.setMouseTracking(True)
        self.shutdown_btn.setLayoutDirection(Qt.LeftToRight)
        self.shutdown_btn.setAutoFillBackground(False)
        self.shutdown_btn.setStyleSheet(
            "QPushButton{\n"
            "	border: none;\n"
            "	background: none;\n"
            "}\n"
            "\n"
            "QPushButton::hover{\n"
            "	background: white;\n"
            "	border: 1px raised;\n"
            "	border-radius: 12px;\n"
            "}"
        )
        icon = QIcon()
        icon.addFile(":/img/img/power.png", QSize(), QIcon.Normal, QIcon.Off)
        self.shutdown_btn.setIcon(icon)
        self.shutdown_btn.setIconSize(QSize(32, 32))
        self.shutdown_btn.setAutoRepeat(False)
        self.shutdown_btn.setAutoExclusive(False)
        self.shutdown_btn.setAutoDefault(False)
        self.shutdown_btn.setFlat(False)
        self.disconnect_btn = QPushButton(self.QSPR_display)
        self.disconnect_btn.setObjectName("disconnect_btn")
        self.disconnect_btn.setGeometry(QRect(10, 25, 30, 30))
        sizePolicy1.setHeightForWidth(
            self.disconnect_btn.sizePolicy().hasHeightForWidth()
        )
        self.disconnect_btn.setSizePolicy(sizePolicy1)
        self.disconnect_btn.setMinimumSize(QSize(30, 30))
        self.disconnect_btn.setMaximumSize(QSize(30, 30))
        self.disconnect_btn.setFont(font2)
        self.disconnect_btn.setMouseTracking(True)
        self.disconnect_btn.setLayoutDirection(Qt.LeftToRight)
        self.disconnect_btn.setAutoFillBackground(False)
        self.disconnect_btn.setStyleSheet(
            "QPushButton{\n"
            "	border: none;\n"
            "	background: none;\n"
            "}\n"
            "\n"
            "QPushButton::hover{\n"
            "	background: white;\n"
            "	border: 1px raised;\n"
            "	border-radius: 12px;\n"
            "}"
        )
        icon1 = QIcon()
        icon1.addFile(":/img/img/disconnect.png", QSize(), QIcon.Normal, QIcon.Off)
        self.disconnect_btn.setIcon(icon1)
        self.disconnect_btn.setIconSize(QSize(34, 34))
        self.disconnect_btn.setAutoRepeat(False)
        self.disconnect_btn.setAutoExclusive(False)
        self.disconnect_btn.setAutoDefault(False)
        self.disconnect_btn.setFlat(False)
        self.temp_display = QFrame(self.QSPR_display)
        self.temp_display.setObjectName("temp_display")
        self.temp_display.setGeometry(QRect(90, 25, 71, 25))
        font3 = QFont()
        font3.setBold(False)
        self.temp_display.setFont(font3)
        self.temp_display.setFrameShape(QFrame.StyledPanel)
        self.temp_display.setFrameShadow(QFrame.Raised)
        self.temp1 = QLabel(self.temp_display)
        self.temp1.setObjectName("temp1")
        self.temp1.setGeometry(QRect(0, 5, 40, 16))
        self.temp1.setFont(font3)
        self.temp1.setAlignment(Qt.AlignCenter)
        self.label_7 = QLabel(self.temp_display)
        self.label_7.setObjectName("label_7")
        self.label_7.setGeometry(QRect(40, 5, 31, 16))
        self.label_7.setMinimumSize(QSize(10, 10))
        self.label_7.setPixmap(QPixmap(":/img/img/deg_c.png"))
        self.cartridge_display = QFrame(self.QSPR_display)
        self.cartridge_display.setObjectName("cartridge_display")
        self.cartridge_display.setGeometry(QRect(0, 60, 261, 51))
        self.cartridge_display.setFont(font3)
        self.cartridge_display.setFrameShape(QFrame.StyledPanel)
        self.cartridge_display.setFrameShadow(QFrame.Raised)
        self.label = QLabel(self.cartridge_display)
        self.label.setObjectName("label")
        self.label.setGeometry(QRect(10, 5, 71, 41))
        font4 = QFont()
        font4.setFamilies(["Segoe UI"])
        font4.setPointSize(9)
        self.label.setFont(font4)
        self.label.setAlignment(Qt.AlignLeading | Qt.AlignLeft | Qt.AlignTop)
        self.label.setMargin(1)
        self.label_3 = QLabel(self.cartridge_display)
        self.label_3.setObjectName("label_3")
        self.label_3.setGeometry(QRect(170, 5, 51, 41))
        self.label_3.setFont(font4)
        self.label_3.setAlignment(Qt.AlignLeading | Qt.AlignLeft | Qt.AlignTop)
        self.label_3.setMargin(1)
        self.ctrls_frame = QFrame(self.QSPR_display)
        self.ctrls_frame.setObjectName("ctrls_frame")
        self.ctrls_frame.setGeometry(QRect(70, 10, 191, 101))
        self.ctrls_frame.setFrameShape(QFrame.StyledPanel)
        self.ctrls_frame.setFrameShadow(QFrame.Raised)
        self.quick_calibrate_btn = QPushButton(self.ctrls_frame)
        self.quick_calibrate_btn.setObjectName("quick_calibrate_btn")
        self.quick_calibrate_btn.setGeometry(QRect(100, 10, 81, 31))
        sizePolicy1.setHeightForWidth(
            self.quick_calibrate_btn.sizePolicy().hasHeightForWidth()
        )
        self.quick_calibrate_btn.setSizePolicy(sizePolicy1)
        font5 = QFont()
        font5.setFamilies(["Segoe UI"])
        font5.setPointSize(9)
        font5.setBold(False)
        self.quick_calibrate_btn.setFont(font5)
        self.quick_calibrate_btn.setStyleSheet(
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
        self.adj_up_btn = QPushButton(self.ctrls_frame)
        self.adj_up_btn.setObjectName("adj_up_btn")
        self.adj_up_btn.setGeometry(QRect(155, 55, 20, 20))
        sizePolicy1.setHeightForWidth(self.adj_up_btn.sizePolicy().hasHeightForWidth())
        self.adj_up_btn.setSizePolicy(sizePolicy1)
        self.adj_up_btn.setMinimumSize(QSize(20, 20))
        self.adj_up_btn.setMaximumSize(QSize(20, 20))
        self.adj_up_btn.setFont(font2)
        self.adj_up_btn.setMouseTracking(True)
        self.adj_up_btn.setLayoutDirection(Qt.LeftToRight)
        self.adj_up_btn.setAutoFillBackground(False)
        self.adj_up_btn.setStyleSheet(
            "QPushButton{\n"
            "	border: none;\n"
            "	background: none;\n"
            "}\n"
            "\n"
            "QPushButton::hover{\n"
            "	background: white;\n"
            "	border: 1px raised;\n"
            "	border-radius: 12px;\n"
            "}"
        )
        icon2 = QIcon()
        icon2.addFile(":/img/img/adj_up.png", QSize(), QIcon.Normal, QIcon.Off)
        self.adj_up_btn.setIcon(icon2)
        self.adj_up_btn.setIconSize(QSize(34, 34))
        self.adj_up_btn.setAutoRepeat(False)
        self.adj_up_btn.setAutoExclusive(False)
        self.adj_up_btn.setAutoDefault(False)
        self.adj_up_btn.setFlat(False)
        self.adj_down_btn = QPushButton(self.ctrls_frame)
        self.adj_down_btn.setObjectName("adj_down_btn")
        self.adj_down_btn.setGeometry(QRect(155, 75, 20, 20))
        sizePolicy1.setHeightForWidth(
            self.adj_down_btn.sizePolicy().hasHeightForWidth()
        )
        self.adj_down_btn.setSizePolicy(sizePolicy1)
        self.adj_down_btn.setMinimumSize(QSize(20, 20))
        self.adj_down_btn.setMaximumSize(QSize(20, 20))
        self.adj_down_btn.setFont(font2)
        self.adj_down_btn.setMouseTracking(True)
        self.adj_down_btn.setLayoutDirection(Qt.LeftToRight)
        self.adj_down_btn.setAutoFillBackground(False)
        self.adj_down_btn.setStyleSheet(
            "QPushButton{\n"
            "	border: none;\n"
            "	background: none;\n"
            "}\n"
            "\n"
            "QPushButton::hover{\n"
            "	background: white;\n"
            "	border: 1px raised;\n"
            "	border-radius: 12px;\n"
            "}"
        )
        icon3 = QIcon()
        icon3.addFile(":/img/img/adj_down.png", QSize(), QIcon.Normal, QIcon.Off)
        self.adj_down_btn.setIcon(icon3)
        self.adj_down_btn.setIconSize(QSize(34, 34))
        self.adj_down_btn.setAutoRepeat(False)
        self.adj_down_btn.setAutoExclusive(False)
        self.adj_down_btn.setAutoDefault(False)
        self.adj_down_btn.setFlat(False)
        self.crt_down_btn = QPushButton(self.ctrls_frame)
        self.crt_down_btn.setObjectName("crt_down_btn")
        self.crt_down_btn.setGeometry(QRect(50, 60, 35, 35))
        sizePolicy1.setHeightForWidth(
            self.crt_down_btn.sizePolicy().hasHeightForWidth()
        )
        self.crt_down_btn.setSizePolicy(sizePolicy1)
        self.crt_down_btn.setMinimumSize(QSize(35, 35))
        self.crt_down_btn.setMaximumSize(QSize(35, 35))
        self.crt_down_btn.setFont(font2)
        self.crt_down_btn.setMouseTracking(True)
        self.crt_down_btn.setLayoutDirection(Qt.LeftToRight)
        self.crt_down_btn.setAutoFillBackground(False)
        self.crt_down_btn.setStyleSheet(
            "QPushButton{\n"
            "	border: none;\n"
            "	background: none;\n"
            "}\n"
            "\n"
            "QPushButton::hover{\n"
            "	background: white;\n"
            "	border: 1px raised;\n"
            "	border-radius: 12px;\n"
            "}"
        )
        icon4 = QIcon()
        icon4.addFile(":/img/img/crt_down.png", QSize(), QIcon.Normal, QIcon.Off)
        self.crt_down_btn.setIcon(icon4)
        self.crt_down_btn.setIconSize(QSize(34, 34))
        self.crt_down_btn.setAutoRepeat(False)
        self.crt_down_btn.setAutoExclusive(False)
        self.crt_down_btn.setAutoDefault(False)
        self.crt_down_btn.setFlat(False)
        self.crt_up_btn = QPushButton(self.ctrls_frame)
        self.crt_up_btn.setObjectName("crt_up_btn")
        self.crt_up_btn.setGeometry(QRect(10, 60, 35, 35))
        sizePolicy1.setHeightForWidth(self.crt_up_btn.sizePolicy().hasHeightForWidth())
        self.crt_up_btn.setSizePolicy(sizePolicy1)
        self.crt_up_btn.setMinimumSize(QSize(35, 35))
        self.crt_up_btn.setMaximumSize(QSize(35, 35))
        self.crt_up_btn.setFont(font2)
        self.crt_up_btn.setMouseTracking(True)
        self.crt_up_btn.setLayoutDirection(Qt.LeftToRight)
        self.crt_up_btn.setAutoFillBackground(False)
        self.crt_up_btn.setStyleSheet(
            "QPushButton{\n"
            "	border: none;\n"
            "	background: none;\n"
            "}\n"
            "\n"
            "QPushButton::hover{\n"
            "	background: white;\n"
            "	border: 1px raised;\n"
            "	border-radius: 12px;\n"
            "}"
        )
        icon5 = QIcon()
        icon5.addFile(":/img/img/crt_up.png", QSize(), QIcon.Normal, QIcon.Off)
        self.crt_up_btn.setIcon(icon5)
        self.crt_up_btn.setIconSize(QSize(34, 34))
        self.crt_up_btn.setAutoRepeat(False)
        self.crt_up_btn.setAutoExclusive(False)
        self.crt_up_btn.setAutoDefault(False)
        self.crt_up_btn.setFlat(False)

        self.verticalLayout.addWidget(self.QSPR_display)

        self.retranslateUi(QSPR)

        self.shutdown_btn.setDefault(False)
        self.disconnect_btn.setDefault(False)
        self.adj_up_btn.setDefault(False)
        self.adj_down_btn.setDefault(False)
        self.crt_down_btn.setDefault(False)
        self.crt_up_btn.setDefault(False)

        QMetaObject.connectSlotsByName(QSPR)

    # setupUi

    def retranslateUi(self, QSPR):
        QSPR.setWindowTitle(QCoreApplication.translate("QSPR", "Form", None))
        self.QSPR_display.setTitle(QCoreApplication.translate("QSPR", "QSPR", None))
        # if QT_CONFIG(tooltip)
        self.shutdown_btn.setToolTip(
            QCoreApplication.translate("QSPR", "Power Off QSPR", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.shutdown_btn.setText("")
        # if QT_CONFIG(tooltip)
        self.disconnect_btn.setToolTip(
            QCoreApplication.translate("QSPR", "Disconnect QSPR", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.disconnect_btn.setText("")
        self.temp1.setText(QCoreApplication.translate("QSPR", "##.#", None))
        self.label_7.setText("")
        self.label.setText(
            QCoreApplication.translate("QSPR", "Cartridge\nControls", None)
        )
        self.label_3.setText(QCoreApplication.translate("QSPR", "Fine\nAdjust", None))
        # if QT_CONFIG(tooltip)
        self.quick_calibrate_btn.setToolTip(
            QCoreApplication.translate("QSPR", "Calibrate QSPR", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.quick_calibrate_btn.setText(
            QCoreApplication.translate("QSPR", "Calibrate", None)
        )
        # if QT_CONFIG(tooltip)
        self.adj_up_btn.setToolTip(
            QCoreApplication.translate("QSPR", "Adjust Up", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.adj_up_btn.setText("")
        # if QT_CONFIG(tooltip)
        self.adj_down_btn.setToolTip(
            QCoreApplication.translate("QSPR", "Adjust Down", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.adj_down_btn.setText("")
        # if QT_CONFIG(tooltip)
        self.crt_down_btn.setToolTip(
            QCoreApplication.translate("QSPR", "Cartrdige Down", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.crt_down_btn.setText("")
        # if QT_CONFIG(tooltip)
        self.crt_up_btn.setToolTip(
            QCoreApplication.translate("QSPR", "Cartridge Up", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.crt_up_btn.setText("")

    # retranslateUi
