# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'sidebar.ui'
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
from PySide6.QtWidgets import (QApplication, QFrame, QGridLayout, QLabel,
    QSizePolicy, QVBoxLayout, QWidget)

class Ui_Sidebar(object):
    def setupUi(self, Sidebar):
        if not Sidebar.objectName():
            Sidebar.setObjectName(u"Sidebar")
        Sidebar.resize(380, 700)
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(Sidebar.sizePolicy().hasHeightForWidth())
        Sidebar.setSizePolicy(sizePolicy)
        Sidebar.setMinimumSize(QSize(380, 700))
        Sidebar.setMaximumSize(QSize(381, 10000))
        font = QFont()
        font.setFamilies([u"Segoe UI"])
        Sidebar.setFont(font)
        Sidebar.setStyleSheet(u"")
        self.gridLayout = QGridLayout(Sidebar)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setHorizontalSpacing(0)
        self.gridLayout.setVerticalSpacing(2)
        self.gridLayout.setContentsMargins(0, 0, 0, 5)
        self.line = QFrame(Sidebar)
        self.line.setObjectName(u"line")
        self.line.setFrameShadow(QFrame.Raised)
        self.line.setLineWidth(1)
        self.line.setFrameShape(QFrame.VLine)

        self.gridLayout.addWidget(self.line, 2, 0, 1, 1)

        self.verticalLayout = QVBoxLayout()
        self.verticalLayout.setSpacing(2)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, -1, 0, 0)
        self.label_2 = QLabel(Sidebar)
        self.label_2.setObjectName(u"label_2")
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.label_2.sizePolicy().hasHeightForWidth())
        self.label_2.setSizePolicy(sizePolicy1)
        self.label_2.setMaximumSize(QSize(16777215, 30))
        font1 = QFont()
        font1.setFamilies([u"Segoe UI"])
        font1.setPointSize(10)
        font1.setBold(True)
        self.label_2.setFont(font1)
        self.label_2.setAlignment(Qt.AlignBottom|Qt.AlignHCenter)

        self.verticalLayout.addWidget(self.label_2, 0, Qt.AlignHCenter)

        self.device_frame = QFrame(Sidebar)
        self.device_frame.setObjectName(u"device_frame")
        sizePolicy2 = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.device_frame.sizePolicy().hasHeightForWidth())
        self.device_frame.setSizePolicy(sizePolicy2)
        self.device_frame.setMinimumSize(QSize(360, 580))
        self.device_frame.setMaximumSize(QSize(380, 16777215))
        self.device_frame.setStyleSheet(u"")
        self.device_frame.setFrameShape(QFrame.StyledPanel)
        self.device_frame.setFrameShadow(QFrame.Raised)

        self.verticalLayout.addWidget(self.device_frame, 0, Qt.AlignHCenter)

        self.label = QLabel(Sidebar)
        self.label.setObjectName(u"label")
        self.label.setMaximumSize(QSize(16777215, 30))
        self.label.setFont(font1)
        self.label.setAlignment(Qt.AlignBottom|Qt.AlignHCenter)

        self.verticalLayout.addWidget(self.label, 0, Qt.AlignHCenter)

        self.kinetic_frame = QFrame(Sidebar)
        self.kinetic_frame.setObjectName(u"kinetic_frame")
        sizePolicy2.setHeightForWidth(self.kinetic_frame.sizePolicy().hasHeightForWidth())
        self.kinetic_frame.setSizePolicy(sizePolicy2)
        self.kinetic_frame.setMinimumSize(QSize(360, 450))
        self.kinetic_frame.setMaximumSize(QSize(380, 500))
        self.kinetic_frame.setStyleSheet(u"")
        self.kinetic_frame.setFrameShape(QFrame.StyledPanel)
        self.kinetic_frame.setFrameShadow(QFrame.Raised)

        self.verticalLayout.addWidget(self.kinetic_frame, 0, Qt.AlignHCenter)


        self.gridLayout.addLayout(self.verticalLayout, 2, 1, 1, 1)


        self.retranslateUi(Sidebar)

        QMetaObject.connectSlotsByName(Sidebar)
    # setupUi

    def retranslateUi(self, Sidebar):
        Sidebar.setWindowTitle(QCoreApplication.translate("Sidebar", u"Form", None))
        self.label_2.setText(QCoreApplication.translate("Sidebar", u"Connected Devices", None))
        self.label.setText(QCoreApplication.translate("Sidebar", u"Kinetic Controls", None))
    # retranslateUi

