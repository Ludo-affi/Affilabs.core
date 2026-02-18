################################################################################
## Form generated from reading UI file 'KNX2.ui'
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


class Ui_KNX2:
    def setupUi(self, KNX2):
        if not KNX2.objectName():
            KNX2.setObjectName("KNX2")
        KNX2.resize(260, 80)
        KNX2.setMinimumSize(QSize(260, 80))
        KNX2.setMaximumSize(QSize(260, 80))
        font = QFont()
        font.setFamilies(["Segoe UI"])
        KNX2.setFont(font)
        KNX2.setStyleSheet(
            "QGroupBox#KnxBox::title{\n"
            "\n"
            "	margin: 0px 5px 0px 5px;\n"
            "	color: rgb(255, 255, 255);\n"
            "	background-color:rgb(46, 48, 227);\n"
            "\n"
            "}\n"
            "\n"
            "QGroupBox#KnxBox{\n"
            "	\n"
            "	border: 2px solid rgba(46, 48, 227, 150);\n"
            "	border-radius: 3px;\n"
            "\n"
            "}",
        )
        self.verticalLayout = QVBoxLayout(KNX2)
        self.verticalLayout.setObjectName("verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.KnxBox = QGroupBox(KNX2)
        self.KnxBox.setObjectName("KnxBox")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.KnxBox.sizePolicy().hasHeightForWidth())
        self.KnxBox.setSizePolicy(sizePolicy)
        self.KnxBox.setMinimumSize(QSize(260, 80))
        self.KnxBox.setMaximumSize(QSize(260, 80))
        font1 = QFont()
        font1.setFamilies(["Segoe UI"])
        font1.setPointSize(9)
        font1.setBold(True)
        self.KnxBox.setFont(font1)
        self.KnxBox.setStyleSheet(
            "QGroupBox#KnxBox::title{\n"
            "\n"
            "	margin: 0px 5px 0px 5px;\n"
            "	color: rgb(255, 255, 255);\n"
            "	background-color:rgb(46, 48, 227);\n"
            "	border-radius: 3px;\n"
            "\n"
            "}\n"
            "\n"
            "QGroupBox#KnxBox{\n"
            "	\n"
            "	border: 2px solid rgba(46, 48, 227, 150);\n"
            "	border-radius: 3px;\n"
            "\n"
            "}",
        )
        self.disconnect_btn = QPushButton(self.KnxBox)
        self.disconnect_btn.setObjectName("disconnect_btn")
        self.disconnect_btn.setGeometry(QRect(10, 25, 30, 30))
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
        self.shutdown_btn = QPushButton(self.KnxBox)
        self.shutdown_btn.setObjectName("shutdown_btn")
        self.shutdown_btn.setGeometry(QRect(50, 25, 30, 30))
        sizePolicy1.setHeightForWidth(
            self.shutdown_btn.sizePolicy().hasHeightForWidth(),
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
            "}",
        )
        icon1 = QIcon()
        icon1.addFile(":/img/img/power.png", QSize(), QIcon.Normal, QIcon.Off)
        self.shutdown_btn.setIcon(icon1)
        self.shutdown_btn.setIconSize(QSize(32, 32))
        self.shutdown_btn.setAutoRepeat(False)
        self.shutdown_btn.setAutoExclusive(False)
        self.shutdown_btn.setAutoDefault(False)
        self.shutdown_btn.setFlat(False)
        self.temp_display = QFrame(self.KnxBox)
        self.temp_display.setObjectName("temp_display")
        self.temp_display.setGeometry(QRect(90, 30, 161, 22))
        font3 = QFont()
        font3.setBold(False)
        self.temp_display.setFont(font3)
        self.temp_display.setFrameShape(QFrame.StyledPanel)
        self.temp_display.setFrameShadow(QFrame.Raised)
        self.temp1 = QLabel(self.temp_display)
        self.temp1.setObjectName("temp1")
        self.temp1.setGeometry(QRect(90, 0, 40, 16))
        self.temp1.setFont(font3)
        self.temp1.setAlignment(Qt.AlignCenter)
        self.label_7 = QLabel(self.temp_display)
        self.label_7.setObjectName("label_7")
        self.label_7.setGeometry(QRect(130, 0, 31, 16))
        self.label_7.setMinimumSize(QSize(10, 10))
        self.label_7.setPixmap(QPixmap(":/img/img/deg_c.png"))
        self.label_7.setAlignment(Qt.AlignLeading | Qt.AlignLeft | Qt.AlignVCenter)
        self.label_8 = QLabel(self.temp_display)
        self.label_8.setObjectName("label_8")
        self.label_8.setGeometry(QRect(0, 0, 91, 16))
        self.label_8.setMinimumSize(QSize(10, 10))
        self.label_8.setAlignment(Qt.AlignCenter)

        self.verticalLayout.addWidget(self.KnxBox)

        self.retranslateUi(KNX2)

        self.disconnect_btn.setDefault(False)
        self.shutdown_btn.setDefault(False)

        QMetaObject.connectSlotsByName(KNX2)

    # setupUi

    def retranslateUi(self, KNX2):
        KNX2.setWindowTitle(QCoreApplication.translate("KNX2", "Form", None))
        self.KnxBox.setTitle(QCoreApplication.translate("KNX2", "Kinetics", None))
        # if QT_CONFIG(tooltip)
        self.disconnect_btn.setToolTip(
            QCoreApplication.translate("KNX2", "Disconnect KNX2", None),
        )
        # endif // QT_CONFIG(tooltip)
        self.disconnect_btn.setText("")
        # if QT_CONFIG(tooltip)
        self.shutdown_btn.setToolTip(
            QCoreApplication.translate("KNX2", "Power Off KNX2", None),
        )
        # endif // QT_CONFIG(tooltip)
        self.shutdown_btn.setText("")
        self.temp1.setText(QCoreApplication.translate("KNX2", "##.#", None))
        self.label_7.setText("")
        self.label_8.setText(
            QCoreApplication.translate(
                "KNX2",
                "<html><head/><body><p>Temperature:</p></body></html>",
                None,
            ),
        )

    # retranslateUi
