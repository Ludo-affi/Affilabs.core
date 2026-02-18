################################################################################
## Form generated from reading UI file 'P4SPR.ui'
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


class Ui_P4SPR_2:
    def setupUi(self, P4SPR_2):
        if not P4SPR_2.objectName():
            P4SPR_2.setObjectName("P4SPR_2")
        P4SPR_2.resize(260, 80)
        P4SPR_2.setMinimumSize(QSize(260, 80))
        P4SPR_2.setMaximumSize(QSize(260, 80))
        font = QFont()
        font.setFamilies(["Segoe UI"])
        P4SPR_2.setFont(font)
        self.verticalLayout = QVBoxLayout(P4SPR_2)
        self.verticalLayout.setObjectName("verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.P4SPR = QGroupBox(P4SPR_2)
        self.P4SPR.setObjectName("P4SPR")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.P4SPR.sizePolicy().hasHeightForWidth())
        self.P4SPR.setSizePolicy(sizePolicy)
        self.P4SPR.setMinimumSize(QSize(260, 80))
        self.P4SPR.setMaximumSize(QSize(260, 80))
        font1 = QFont()
        font1.setFamilies(["Segoe UI"])
        font1.setPointSize(9)
        font1.setBold(True)
        self.P4SPR.setFont(font1)
        self.P4SPR.setStyleSheet(
            "QGroupBox#P4SPR::title{\n"
            "\n"
            "	margin: 0px 5px 0px 5px;\n"
            "	color: rgb(255, 255, 255);\n"
            "	background-color:rgb(46, 48, 227);\n"
            "	border-radius: 3px;\n"
            "\n"
            "}\n"
            "\n"
            "QGroupBox#P4SPR{\n"
            "	\n"
            "	border: 2px solid rgba(46, 48, 227, 150);\n"
            "	border-radius: 3px;\n"
            "\n"
            "}",
        )
        self.disconnect_btn = QPushButton(self.P4SPR)
        self.disconnect_btn.setObjectName("disconnect_btn")
        self.disconnect_btn.setGeometry(QRect(10, 30, 30, 30))
        sizePolicy1 = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(
            self.disconnect_btn.sizePolicy().hasHeightForWidth(),
        )
        self.disconnect_btn.setSizePolicy(sizePolicy1)
        self.disconnect_btn.setMinimumSize(QSize(30, 30))
        self.disconnect_btn.setMaximumSize(QSize(30, 30))
        font2 = QFont()
        font2.setPointSize(5)
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
            "}",
        )
        icon = QIcon()
        icon.addFile(":/img/img/disconnect.png", QSize(), QIcon.Normal, QIcon.Off)
        self.disconnect_btn.setIcon(icon)
        self.disconnect_btn.setIconSize(QSize(34, 34))
        self.disconnect_btn.setAutoRepeat(False)
        self.disconnect_btn.setAutoExclusive(False)
        self.disconnect_btn.setAutoDefault(False)
        self.disconnect_btn.setFlat(False)
        self.ctrls_frame = QFrame(self.P4SPR)
        self.ctrls_frame.setObjectName("ctrls_frame")
        self.ctrls_frame.setGeometry(QRect(130, 20, 121, 51))
        self.ctrls_frame.setFrameShape(QFrame.StyledPanel)
        self.ctrls_frame.setFrameShadow(QFrame.Raised)
        self.quick_calibrate_btn = QPushButton(self.ctrls_frame)
        self.quick_calibrate_btn.setObjectName("quick_calibrate_btn")
        self.quick_calibrate_btn.setGeometry(QRect(10, 10, 101, 31))
        sizePolicy1.setHeightForWidth(
            self.quick_calibrate_btn.sizePolicy().hasHeightForWidth(),
        )
        self.quick_calibrate_btn.setSizePolicy(sizePolicy1)
        font3 = QFont()
        font3.setFamilies(["Segoe UI"])
        font3.setPointSize(9)
        font3.setBold(False)
        self.quick_calibrate_btn.setFont(font3)
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
            "}",
        )
        self.temp_display = QFrame(self.P4SPR)
        self.temp_display.setObjectName("temp_display")
        self.temp_display.setGeometry(QRect(40, 25, 91, 41))
        font4 = QFont()
        font4.setBold(False)
        self.temp_display.setFont(font4)
        self.temp_display.setFrameShape(QFrame.StyledPanel)
        self.temp_display.setFrameShadow(QFrame.Raised)
        self.temp1 = QLabel(self.temp_display)
        self.temp1.setObjectName("temp1")
        self.temp1.setGeometry(QRect(10, 20, 51, 16))
        self.temp1.setFont(font4)
        self.temp1.setAlignment(Qt.AlignCenter)
        self.label_7 = QLabel(self.temp_display)
        self.label_7.setObjectName("label_7")
        self.label_7.setGeometry(QRect(50, 20, 31, 16))
        self.label_7.setMinimumSize(QSize(10, 10))
        self.label_7.setPixmap(QPixmap(":/img/img/deg_c.png"))
        self.label_8 = QLabel(self.temp_display)
        self.label_8.setObjectName("label_8")
        self.label_8.setGeometry(QRect(0, 0, 91, 16))
        self.label_8.setMinimumSize(QSize(10, 10))
        self.label_8.setAlignment(Qt.AlignCenter)

        self.verticalLayout.addWidget(self.P4SPR)

        self.retranslateUi(P4SPR_2)

        self.disconnect_btn.setDefault(False)

        QMetaObject.connectSlotsByName(P4SPR_2)

    # setupUi

    def retranslateUi(self, P4SPR_2):
        P4SPR_2.setWindowTitle(QCoreApplication.translate("P4SPR_2", "Form", None))
        self.P4SPR.setTitle(QCoreApplication.translate("P4SPR_2", "SPR", None))
        # if QT_CONFIG(tooltip)
        self.disconnect_btn.setToolTip(
            QCoreApplication.translate("P4SPR_2", "Disconnect P4SPR", None),
        )
        # endif // QT_CONFIG(tooltip)
        self.disconnect_btn.setText("")
        self.quick_calibrate_btn.setText(
            QCoreApplication.translate("P4SPR_2", "Calibrate", None),
        )
        self.temp1.setText("")
        self.label_7.setText("")
        self.label_8.setText(
            QCoreApplication.translate(
                "P4SPR_2",
                "<html><head/><body><p>Temp:</p></body></html>",
                None,
            ),
        )

    # retranslateUi
