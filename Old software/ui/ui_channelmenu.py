# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'channelmenu.ui'
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
from PySide6.QtWidgets import (QApplication, QDialog, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QRadioButton, QCheckBox,
    QSizePolicy, QSpacerItem, QVBoxLayout, QWidget)
import ui.ai_rc

class Ui_ChannelMenu(object):
    def setupUi(self, ChannelMenu):
        if not ChannelMenu.objectName():
            ChannelMenu.setObjectName(u"ChannelMenu")
        ChannelMenu.resize(350, 350)
        font = QFont()
        font.setFamilies([u"Segoe UI"])
        ChannelMenu.setFont(font)
        icon = QIcon()
        icon.addFile(u":/img/img/affinite2.ico", QSize(), QIcon.Normal, QIcon.Off)
        ChannelMenu.setWindowIcon(icon)
        self.verticalLayout = QVBoxLayout(ChannelMenu)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.filter = QGroupBox(ChannelMenu)
        self.filter.setObjectName(u"filter")
        font1 = QFont()
        font1.setFamilies([u"Segoe UI"])
        font1.setPointSize(9)
        self.filter.setFont(font1)
        self.verticalLayout_2 = QVBoxLayout(self.filter)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(11, 0, 11, 0)
        self.filt_en = QRadioButton(self.filter)
        self.filt_en.setObjectName(u"filt_en")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.filt_en.sizePolicy().hasHeightForWidth())
        self.filt_en.setSizePolicy(sizePolicy)
        self.filt_en.setChecked(True)

        self.horizontalLayout.addWidget(self.filt_en, 0, Qt.AlignHCenter)

        self.filt_off = QRadioButton(self.filter)
        self.filt_off.setObjectName(u"filt_off")
        sizePolicy.setHeightForWidth(self.filt_off.sizePolicy().hasHeightForWidth())
        self.filt_off.setSizePolicy(sizePolicy)
        self.filt_off.setChecked(False)

        self.horizontalLayout.addWidget(self.filt_off, 0, Qt.AlignHCenter)


        self.verticalLayout_2.addLayout(self.horizontalLayout)

        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setSpacing(11)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(11, -1, 11, -1)
        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer_2)

        self.label_5 = QLabel(self.filter)
        self.label_5.setObjectName(u"label_5")
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.label_5.sizePolicy().hasHeightForWidth())
        self.label_5.setSizePolicy(sizePolicy1)
        self.label_5.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignVCenter)

        self.horizontalLayout_2.addWidget(self.label_5, 0, Qt.AlignLeft)

        self.filt_win = QLineEdit(self.filter)
        self.filt_win.setObjectName(u"filt_win")
        sizePolicy.setHeightForWidth(self.filt_win.sizePolicy().hasHeightForWidth())
        self.filt_win.setSizePolicy(sizePolicy)
        self.filt_win.setMaximumSize(QSize(60, 16777215))
        self.filt_win.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_2.addWidget(self.filt_win, 0, Qt.AlignLeft)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer)


        self.verticalLayout_2.addLayout(self.horizontalLayout_2)


        self.verticalLayout.addWidget(self.filter)

        self.groupBox = QGroupBox(ChannelMenu)
        self.groupBox.setObjectName(u"groupBox")
        self.groupBox.setEnabled(True)
        font2 = QFont()
        font2.setFamilies([u"Segoe UI"])
        font2.setPointSize(9)
        font2.setBold(False)
        self.groupBox.setFont(font2)
        self.groupBox.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignVCenter)
        self.verticalLayout_3 = QVBoxLayout(self.groupBox)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_4 = QHBoxLayout()
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(15, -1, -1, -1)
        self.noRef = QRadioButton(self.groupBox)
        self.noRef.setObjectName(u"noRef")
        self.noRef.setFont(font2)
        self.noRef.setChecked(True)

        self.horizontalLayout_4.addWidget(self.noRef)

        self.channelA = QRadioButton(self.groupBox)
        self.channelA.setObjectName(u"channelA")
        self.channelA.setFont(font2)
        self.channelA.setChecked(False)

        self.horizontalLayout_4.addWidget(self.channelA)

        self.channelB = QRadioButton(self.groupBox)
        self.channelB.setObjectName(u"channelB")
        self.channelB.setFont(font2)

        self.horizontalLayout_4.addWidget(self.channelB)

        self.channelC = QRadioButton(self.groupBox)
        self.channelC.setObjectName(u"channelC")
        self.channelC.setFont(font2)

        self.horizontalLayout_4.addWidget(self.channelC)

        self.channelD = QRadioButton(self.groupBox)
        self.channelD.setObjectName(u"channelD")
        self.channelD.setFont(font2)
        self.channelD.setChecked(False)

        self.horizontalLayout_4.addWidget(self.channelD)


        self.verticalLayout_3.addLayout(self.horizontalLayout_4)


        self.verticalLayout.addWidget(self.groupBox)

        self.groupBox_3 = QGroupBox(ChannelMenu)
        self.groupBox_3.setObjectName(u"groupBox_3")
        self.groupBox_3.setEnabled(True)
        self.groupBox_3.setFont(font2)
        self.horizontalLayout_3 = QHBoxLayout(self.groupBox_3)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_5 = QHBoxLayout()
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.label_2 = QLabel(self.groupBox_3)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setMinimumSize(QSize(150, 0))
        self.label_2.setMaximumSize(QSize(150, 16777215))
        self.label_2.setFont(font2)
        self.label_2.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_5.addWidget(self.label_2)

        self.unit_ru = QRadioButton(self.groupBox_3)
        self.unit_ru.setObjectName(u"unit_ru")
        self.unit_ru.setChecked(True)

        self.horizontalLayout_5.addWidget(self.unit_ru)

        self.unit_nm = QRadioButton(self.groupBox_3)
        self.unit_nm.setObjectName(u"unit_nm")
        self.unit_nm.setEnabled(True)
        self.unit_nm.setChecked(False)

        self.horizontalLayout_5.addWidget(self.unit_nm)


        self.horizontalLayout_3.addLayout(self.horizontalLayout_5)


        self.verticalLayout.addWidget(self.groupBox_3)

        self.groupBox_2 = QGroupBox(ChannelMenu)
        self.groupBox_2.setObjectName(u"groupBox_2")
        self.horizontalLayout_7 = QHBoxLayout(self.groupBox_2)
        self.horizontalLayout_7.setObjectName(u"horizontalLayout_7")
        self.reset_data = QPushButton(self.groupBox_2)
        self.reset_data.setObjectName(u"reset_data")

        self.horizontalLayout_7.addWidget(self.reset_data)

        self.export_data = QPushButton(self.groupBox_2)
        self.export_data.setObjectName(u"export_data")

        self.horizontalLayout_7.addWidget(self.export_data)


        self.verticalLayout.addWidget(self.groupBox_2)

        self.groupBox_4 = QGroupBox(ChannelMenu)
        self.groupBox_4.setObjectName(u"groupBox_4")
        self.horizontalLayout_8 = QHBoxLayout(self.groupBox_4)
        self.horizontalLayout_8.setObjectName(u"horizontalLayout_8")
        self.colorblind_mode = QCheckBox(self.groupBox_4)
        self.colorblind_mode.setObjectName(u"colorblind_mode")
        self.colorblind_mode.setChecked(False)

        self.horizontalLayout_8.addWidget(self.colorblind_mode)


        self.verticalLayout.addWidget(self.groupBox_4)


        self.retranslateUi(ChannelMenu)

        QMetaObject.connectSlotsByName(ChannelMenu)
    # setupUi

    def retranslateUi(self, ChannelMenu):
        ChannelMenu.setWindowTitle(QCoreApplication.translate("ChannelMenu", u"SPR Settings", None))
        self.filter.setTitle(QCoreApplication.translate("ChannelMenu", u"Data Filtering", None))
        self.filt_en.setText(QCoreApplication.translate("ChannelMenu", u"Enabled", None))
        self.filt_off.setText(QCoreApplication.translate("ChannelMenu", u"Disabled", None))
        self.label_5.setText(QCoreApplication.translate("ChannelMenu", u"Filter Window Size:", None))
        self.filt_win.setText(QCoreApplication.translate("ChannelMenu", u"5", None))
        self.groupBox.setTitle(QCoreApplication.translate("ChannelMenu", u"Reference Channel", None))
        self.noRef.setText(QCoreApplication.translate("ChannelMenu", u"None", None))
        self.channelA.setText(QCoreApplication.translate("ChannelMenu", u" A", None))
        self.channelB.setText(QCoreApplication.translate("ChannelMenu", u"B", None))
        self.channelC.setText(QCoreApplication.translate("ChannelMenu", u"C", None))
        self.channelD.setText(QCoreApplication.translate("ChannelMenu", u"D", None))
        self.groupBox_3.setTitle(QCoreApplication.translate("ChannelMenu", u"Units", None))
        self.label_2.setText(QCoreApplication.translate("ChannelMenu", u"Display Shifts:", None))
        self.unit_ru.setText(QCoreApplication.translate("ChannelMenu", u"RU", None))
        self.unit_nm.setText(QCoreApplication.translate("ChannelMenu", u"nm", None))
        self.groupBox_2.setTitle(QCoreApplication.translate("ChannelMenu", u"Live Data", None))
        self.reset_data.setText(QCoreApplication.translate("ChannelMenu", u"Reset", None))
        self.export_data.setText(QCoreApplication.translate("ChannelMenu", u"Export", None))
        self.groupBox_4.setTitle(QCoreApplication.translate("ChannelMenu", u"Accessibility", None))
        self.colorblind_mode.setText(QCoreApplication.translate("ChannelMenu", u"Colorblind-Friendly Palette", None))
    # retranslateUi

