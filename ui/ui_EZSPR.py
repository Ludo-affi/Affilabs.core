################################################################################
## Form generated from reading UI file 'EZSPR.ui'
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


class Ui_EZSPRForm:
    def setupUi(self, EZSPRForm):
        if not EZSPRForm.objectName():
            EZSPRForm.setObjectName("EZSPRForm")
        EZSPRForm.resize(260, 100)
        EZSPRForm.setMinimumSize(QSize(260, 100))
        EZSPRForm.setMaximumSize(QSize(260, 110))
        font = QFont()
        font.setFamilies(["Segoe UI"])
        EZSPRForm.setFont(font)
        self.verticalLayout = QVBoxLayout(EZSPRForm)
        self.verticalLayout.setObjectName("verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.EZSPR = QGroupBox(EZSPRForm)
        self.EZSPR.setObjectName("EZSPR")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.EZSPR.sizePolicy().hasHeightForWidth())
        self.EZSPR.setSizePolicy(sizePolicy)
        self.EZSPR.setMinimumSize(QSize(260, 100))
        self.EZSPR.setMaximumSize(QSize(260, 100))
        font1 = QFont()
        font1.setFamilies(["Segoe UI"])
        font1.setPointSize(9)
        font1.setBold(True)
        self.EZSPR.setFont(font1)
        self.EZSPR.setStyleSheet(
            "QGroupBox#EZSPR::title{\n"
            "\n"
            "	margin: 0px 5px 0px 5px;\n"
            "	color: rgb(255, 255, 255);\n"
            "	background-color:rgb(46, 48, 227);\n"
            "	border-radius: 3px;\n"
            "\n"
            "}\n"
            "\n"
            "QGroupBox#EZSPR{\n"
            "	\n"
            "	border: 2px solid rgba(46, 48, 227, 150);\n"
            "	border-radius: 3px;\n"
            "\n"
            "}"
        )
        self.EZSPR.setFlat(False)
        self.EZSPR.setCheckable(False)
        self.disconnect_btn = QPushButton(self.EZSPR)
        self.disconnect_btn.setObjectName("disconnect_btn")
        self.disconnect_btn.setGeometry(QRect(10, 28, 30, 30))
        sizePolicy1 = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(
            self.disconnect_btn.sizePolicy().hasHeightForWidth()
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
            "}"
        )
        icon = QIcon()
        icon.addFile(":/img/img/disconnect.png", QSize(), QIcon.Normal, QIcon.Off)
        self.disconnect_btn.setIcon(icon)
        self.disconnect_btn.setIconSize(QSize(34, 34))
        self.disconnect_btn.setAutoRepeat(False)
        self.disconnect_btn.setAutoExclusive(False)
        self.disconnect_btn.setAutoDefault(False)
        self.disconnect_btn.setFlat(False)
        self.shutdown_btn = QPushButton(self.EZSPR)
        self.shutdown_btn.setObjectName("shutdown_btn")
        self.shutdown_btn.setGeometry(QRect(50, 28, 30, 30))
        sizePolicy1.setHeightForWidth(
            self.shutdown_btn.sizePolicy().hasHeightForWidth()
        )
        self.shutdown_btn.setSizePolicy(sizePolicy1)
        self.shutdown_btn.setMinimumSize(QSize(30, 30))
        self.shutdown_btn.setMaximumSize(QSize(30, 30))
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
        icon1 = QIcon()
        icon1.addFile(":/img/img/power.png", QSize(), QIcon.Normal, QIcon.Off)
        self.shutdown_btn.setIcon(icon1)
        self.shutdown_btn.setIconSize(QSize(32, 32))
        self.shutdown_btn.setAutoRepeat(False)
        self.shutdown_btn.setAutoExclusive(False)
        self.shutdown_btn.setAutoDefault(False)
        self.shutdown_btn.setFlat(False)
        self.temp_display = QFrame(self.EZSPR)
        self.temp_display.setObjectName("temp_display")
        self.temp_display.setGeometry(QRect(40, 70, 181, 22))
        font3 = QFont()
        font3.setBold(False)
        self.temp_display.setFont(font3)
        self.temp_display.setFrameShape(QFrame.StyledPanel)
        self.temp_display.setFrameShadow(QFrame.Raised)
        self.temp1 = QLabel(self.temp_display)
        self.temp1.setObjectName("temp1")
        self.temp1.setGeometry(QRect(100, 0, 51, 16))
        self.temp1.setFont(font3)
        self.temp1.setAlignment(Qt.AlignCenter)
        self.label_7 = QLabel(self.temp_display)
        self.label_7.setObjectName("label_7")
        self.label_7.setGeometry(QRect(150, 0, 31, 16))
        self.label_7.setMinimumSize(QSize(10, 10))
        self.label_7.setPixmap(QPixmap(":/img/img/deg_c.png"))
        self.label_8 = QLabel(self.temp_display)
        self.label_8.setObjectName("label_8")
        self.label_8.setGeometry(QRect(10, 0, 91, 16))
        self.label_8.setMinimumSize(QSize(10, 10))
        self.label_8.setAlignment(Qt.AlignCenter)
        self.ctrls_frame = QFrame(self.EZSPR)
        self.ctrls_frame.setObjectName("ctrls_frame")
        self.ctrls_frame.setGeometry(QRect(90, 10, 161, 71))
        self.ctrls_frame.setFrameShape(QFrame.StyledPanel)
        self.ctrls_frame.setFrameShadow(QFrame.Raised)
        self.quick_calibrate_btn = QPushButton(self.ctrls_frame)
        self.quick_calibrate_btn.setObjectName("quick_calibrate_btn")
        self.quick_calibrate_btn.setGeometry(QRect(20, 20, 120, 30))
        sizePolicy1.setHeightForWidth(
            self.quick_calibrate_btn.sizePolicy().hasHeightForWidth()
        )
        self.quick_calibrate_btn.setSizePolicy(sizePolicy1)
        font4 = QFont()
        font4.setFamilies(["Segoe UI"])
        font4.setPointSize(9)
        font4.setBold(False)
        self.quick_calibrate_btn.setFont(font4)
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

        self.verticalLayout.addWidget(self.EZSPR, 0, Qt.AlignTop)

        self.retranslateUi(EZSPRForm)

        self.disconnect_btn.setDefault(False)
        self.shutdown_btn.setDefault(False)

        QMetaObject.connectSlotsByName(EZSPRForm)

    # setupUi

    def retranslateUi(self, EZSPRForm):
        EZSPRForm.setWindowTitle(QCoreApplication.translate("EZSPRForm", "Form", None))
        self.EZSPR.setTitle(QCoreApplication.translate("EZSPRForm", "EZSPR", None))
        # if QT_CONFIG(tooltip)
        self.disconnect_btn.setToolTip(
            QCoreApplication.translate("EZSPRForm", "Disconnect EZSPR", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.disconnect_btn.setText("")
        # if QT_CONFIG(tooltip)
        self.shutdown_btn.setToolTip(
            QCoreApplication.translate("EZSPRForm", "Power Off EZSPR", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.shutdown_btn.setText("")
        self.temp1.setText(QCoreApplication.translate("EZSPRForm", "##.#", None))
        self.label_7.setText("")
        self.label_8.setText(
            QCoreApplication.translate(
                "EZSPRForm",
                "<html><head/><body><p>Temperature:</p></body></html>",
                None,
            )
        )
        # if QT_CONFIG(tooltip)
        self.quick_calibrate_btn.setToolTip(
            QCoreApplication.translate("EZSPRForm", "Calibrate EZSPR", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.quick_calibrate_btn.setText(
            QCoreApplication.translate("EZSPRForm", "Calibrate", None)
        )

    # retranslateUi
