# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'Affipump.ui'
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
from PySide6.QtWidgets import (QApplication, QGroupBox, QHBoxLayout, QPushButton,
    QSizePolicy, QSpacerItem, QVBoxLayout, QWidget)
import ui.ai_rc

class Ui_Affipump(object):
    def setupUi(self, Affipump):
        if not Affipump.objectName():
            Affipump.setObjectName(u"Affipump")
        Affipump.resize(260, 80)
        self.verticalLayout = QVBoxLayout(Affipump)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.groupBox = QGroupBox(Affipump)
        self.groupBox.setObjectName(u"groupBox")
        font = QFont()
        font.setBold(True)
        self.groupBox.setFont(font)
        self.groupBox.setStyleSheet(u"QGroupBox::title{\n"
"\n"
"	margin: 0px 5px 0px 5px;\n"
"	color: rgb(255, 255, 255);\n"
"	background-color:rgb(46, 48, 227);\n"
"	border-radius: 3px;\n"
"\n"
"}\n"
"\n"
"QGroupBox{\n"
"	\n"
"	border: 2px solid rgba(46, 48, 227, 150);\n"
"	border-radius: 3px;\n"
"\n"
"}")
        self.horizontalLayout = QHBoxLayout(self.groupBox)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.disconnect_btn = QPushButton(self.groupBox)
        self.disconnect_btn.setObjectName(u"disconnect_btn")
        self.disconnect_btn.setStyleSheet(u"QPushButton{\n"
"	border: none;\n"
"	background: none;\n"
"}\n"
"\n"
"QPushButton::hover{\n"
"	background: white;\n"
"	border: 1px raised;\n"
"	border-radius: 12px;\n"
"}")
        icon = QIcon()
        icon.addFile(u":/img/img/disconnect.png", QSize(), QIcon.Normal, QIcon.Off)
        self.disconnect_btn.setIcon(icon)
        self.disconnect_btn.setIconSize(QSize(34, 34))

        self.horizontalLayout.addWidget(self.disconnect_btn)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.initialize_btn = QPushButton(self.groupBox)
        self.initialize_btn.setObjectName(u"initialize_btn")
        self.initialize_btn.setMinimumSize(QSize(100, 30))
        self.initialize_btn.setStyleSheet(u"QPushButton {\n"
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

        self.horizontalLayout.addWidget(self.initialize_btn)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout.addItem(self.horizontalSpacer_2)


        self.verticalLayout.addWidget(self.groupBox)


        self.retranslateUi(Affipump)

        QMetaObject.connectSlotsByName(Affipump)
    # setupUi

    def retranslateUi(self, Affipump):
        Affipump.setWindowTitle(QCoreApplication.translate("Affipump", u"Form", None))
        self.groupBox.setTitle(QCoreApplication.translate("Affipump", u"Pumps", None))
        self.disconnect_btn.setText("")
        self.initialize_btn.setText(QCoreApplication.translate("Affipump", u"Initialize", None))
    # retranslateUi

