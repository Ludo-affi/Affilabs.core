# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'qspr_adv_settings.ui'
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
from PySide6.QtWidgets import (QApplication, QGridLayout, QLabel, QLineEdit,
    QPushButton, QSizePolicy, QVBoxLayout, QWidget)
import ui.ai_rc

class Ui_QSPR_Advanced(object):
    def setupUi(self, QSPR_Advanced):
        if not QSPR_Advanced.objectName():
            QSPR_Advanced.setObjectName(u"QSPR_Advanced")
        QSPR_Advanced.resize(300, 300)
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(QSPR_Advanced.sizePolicy().hasHeightForWidth())
        QSPR_Advanced.setSizePolicy(sizePolicy)
        QSPR_Advanced.setMinimumSize(QSize(300, 300))
        QSPR_Advanced.setMaximumSize(QSize(300, 400))
        font = QFont()
        font.setFamilies([u"Segoe UI"])
        QSPR_Advanced.setFont(font)
        QSPR_Advanced.setFocusPolicy(Qt.StrongFocus)
        icon = QIcon()
        icon.addFile(u":/img/img/affinite2.ico", QSize(), QIcon.Normal, QIcon.Off)
        QSPR_Advanced.setWindowIcon(icon)
        QSPR_Advanced.setStyleSheet(u"")
        self.verticalLayout = QVBoxLayout(QSPR_Advanced)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_2 = QVBoxLayout()
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(-1, -1, -1, 10)
        self.label = QLabel(QSPR_Advanced)
        self.label.setObjectName(u"label")
        self.label.setMaximumSize(QSize(16777215, 40))
        font1 = QFont()
        font1.setPointSize(9)
        font1.setBold(True)
        self.label.setFont(font1)
        self.label.setAlignment(Qt.AlignHCenter|Qt.AlignTop)
        self.label.setMargin(10)

        self.verticalLayout_2.addWidget(self.label)

        self.gridLayout = QGridLayout()
        self.gridLayout.setSpacing(10)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(10, 10, 10, 10)
        self.up_time = QLineEdit(QSPR_Advanced)
        self.up_time.setObjectName(u"up_time")
        self.up_time.setMaximumSize(QSize(80, 16777215))
        self.up_time.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.up_time, 2, 1, 1, 1)

        self.label_2 = QLabel(QSPR_Advanced)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignVCenter)

        self.gridLayout.addWidget(self.label_2, 0, 0, 1, 1)

        self.down_time = QLineEdit(QSPR_Advanced)
        self.down_time.setObjectName(u"down_time")
        self.down_time.setMaximumSize(QSize(80, 16777215))
        self.down_time.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.down_time, 3, 1, 1, 1)

        self.s_pos = QLineEdit(QSPR_Advanced)
        self.s_pos.setObjectName(u"s_pos")
        self.s_pos.setMaximumSize(QSize(80, 16777215))
        self.s_pos.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.s_pos, 0, 1, 1, 1)

        self.label_3 = QLabel(QSPR_Advanced)
        self.label_3.setObjectName(u"label_3")

        self.gridLayout.addWidget(self.label_3, 2, 0, 1, 1)

        self.p_pos = QLineEdit(QSPR_Advanced)
        self.p_pos.setObjectName(u"p_pos")
        self.p_pos.setMaximumSize(QSize(80, 16777215))
        self.p_pos.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.p_pos, 1, 1, 1, 1)

        self.label_5 = QLabel(QSPR_Advanced)
        self.label_5.setObjectName(u"label_5")

        self.gridLayout.addWidget(self.label_5, 3, 0, 1, 1)

        self.label_4 = QLabel(QSPR_Advanced)
        self.label_4.setObjectName(u"label_4")

        self.gridLayout.addWidget(self.label_4, 1, 0, 1, 1)

        self.label_6 = QLabel(QSPR_Advanced)
        self.label_6.setObjectName(u"label_6")

        self.gridLayout.addWidget(self.label_6, 4, 0, 1, 1)

        self.adj_time = QLineEdit(QSPR_Advanced)
        self.adj_time.setObjectName(u"adj_time")
        self.adj_time.setMaximumSize(QSize(80, 16777215))
        self.adj_time.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.adj_time, 4, 1, 1, 1)

        self.debounce = QLineEdit(QSPR_Advanced)
        self.debounce.setObjectName(u"debounce")
        self.debounce.setMaximumSize(QSize(80, 16777215))
        self.debounce.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.debounce, 5, 1, 1, 1)

        self.label_7 = QLabel(QSPR_Advanced)
        self.label_7.setObjectName(u"label_7")

        self.gridLayout.addWidget(self.label_7, 5, 0, 1, 1)

        self.label_8 = QLabel(QSPR_Advanced)
        self.label_8.setObjectName(u"label_8")

        self.gridLayout.addWidget(self.label_8, 6, 0, 1, 1)

        self.start_interval = QLineEdit(QSPR_Advanced)
        self.start_interval.setObjectName(u"start_interval")
        self.start_interval.setMaximumSize(QSize(80, 16777215))
        self.start_interval.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.start_interval, 6, 1, 1, 1)


        self.verticalLayout_2.addLayout(self.gridLayout)

        self.set_btn = QPushButton(QSPR_Advanced)
        self.set_btn.setObjectName(u"set_btn")
        sizePolicy1 = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.set_btn.sizePolicy().hasHeightForWidth())
        self.set_btn.setSizePolicy(sizePolicy1)
        self.set_btn.setMinimumSize(QSize(100, 25))
        self.set_btn.setFont(font)
        self.set_btn.setStyleSheet(u"QPushButton {\n"
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

        self.verticalLayout_2.addWidget(self.set_btn, 0, Qt.AlignHCenter|Qt.AlignVCenter)


        self.verticalLayout.addLayout(self.verticalLayout_2)


        self.retranslateUi(QSPR_Advanced)

        QMetaObject.connectSlotsByName(QSPR_Advanced)
    # setupUi

    def retranslateUi(self, QSPR_Advanced):
        QSPR_Advanced.setWindowTitle(QCoreApplication.translate("QSPR_Advanced", u"Advanced Settings", None))
        self.label.setText(QCoreApplication.translate("QSPR_Advanced", u"QSPR Adavanced Parameter Settings", None))
        self.label_2.setText(QCoreApplication.translate("QSPR_Advanced", u"Polarizer S-Position:", None))
        self.label_3.setText(QCoreApplication.translate("QSPR_Advanced", u"Crt. Up Timeout (s):", None))
        self.label_5.setText(QCoreApplication.translate("QSPR_Advanced", u"Crt. Down Timeout (s):", None))
        self.label_4.setText(QCoreApplication.translate("QSPR_Advanced", u"Polarizer P-Position:", None))
        self.label_6.setText(QCoreApplication.translate("QSPR_Advanced", u"Crt. Adj Time (ms):", None))
        self.label_7.setText(QCoreApplication.translate("QSPR_Advanced", u"Current Sense Debounce (ms):", None))
        self.label_8.setText(QCoreApplication.translate("QSPR_Advanced", u"Startup Current Interval (ms):", None))
        self.set_btn.setText(QCoreApplication.translate("QSPR_Advanced", u"Update Settings", None))
    # retranslateUi

