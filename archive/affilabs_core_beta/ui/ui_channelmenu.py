################################################################################
## Form generated from reading UI file 'channelmenu.ui'
##
## Created by: Qt User Interface Compiler version 6.6.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import QCoreApplication, QMetaObject, QSize, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
)

from ui.styles import get_standard_checkbox_style, get_standard_radiobutton_style


class Ui_ChannelMenu:
    def setupUi(self, ChannelMenu):
        if not ChannelMenu.objectName():
            ChannelMenu.setObjectName("ChannelMenu")
        ChannelMenu.resize(350, 350)
        font = QFont()
        font.setFamilies(["Segoe UI"])
        ChannelMenu.setFont(font)
        icon = QIcon()
        icon.addFile(":/img/img/affinite2.ico", QSize(), QIcon.Normal, QIcon.Off)
        ChannelMenu.setWindowIcon(icon)
        self.verticalLayout = QVBoxLayout(ChannelMenu)
        self.verticalLayout.setObjectName("verticalLayout")
        # Standard font for groupbox titles
        font_groupbox = QFont()
        font_groupbox.setFamilies(["Segoe UI"])
        font_groupbox.setPointSize(8)
        # Standard font for general UI elements
        font_standard = QFont()
        font_standard.setFamilies(["Segoe UI"])
        font_standard.setPointSize(9)
        # Get standard styles
        radiobutton_style = get_standard_radiobutton_style()
        checkbox_style = get_standard_checkbox_style()
        self.filter = QGroupBox(ChannelMenu)
        self.filter.setObjectName("filter")
        self.filter.setFont(font_groupbox)
        self.verticalLayout_2 = QVBoxLayout(self.filter)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.horizontalLayout.setContentsMargins(11, 0, 11, 0)
        self.filt_en = QCheckBox(self.filter)
        self.filt_en.setObjectName("filt_en")
        self.filt_en.setStyleSheet(checkbox_style)
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.filt_en.sizePolicy().hasHeightForWidth())
        self.filt_en.setSizePolicy(sizePolicy)
        self.filt_en.setChecked(True)

        self.horizontalLayout.addWidget(self.filt_en, 0, Qt.AlignHCenter)

        self.verticalLayout_2.addLayout(self.horizontalLayout)

        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setSpacing(11)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(11, -1, 11, -1)
        self.horizontalSpacer_2 = QSpacerItem(
            40,
            20,
            QSizePolicy.Expanding,
            QSizePolicy.Minimum,
        )

        self.horizontalLayout_2.addItem(self.horizontalSpacer_2)

        self.label_5 = QLabel(self.filter)
        self.label_5.setObjectName("label_5")
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.label_5.sizePolicy().hasHeightForWidth())
        self.label_5.setSizePolicy(sizePolicy1)
        self.label_5.setAlignment(Qt.AlignLeading | Qt.AlignLeft | Qt.AlignVCenter)

        self.horizontalLayout_2.addWidget(self.label_5, 0, Qt.AlignLeft)

        self.filt_win = QLineEdit(self.filter)
        self.filt_win.setObjectName("filt_win")
        sizePolicy.setHeightForWidth(self.filt_win.sizePolicy().hasHeightForWidth())
        self.filt_win.setSizePolicy(sizePolicy)
        self.filt_win.setMaximumSize(QSize(60, 16777215))
        self.filt_win.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_2.addWidget(self.filt_win, 0, Qt.AlignLeft)

        self.horizontalSpacer = QSpacerItem(
            40,
            20,
            QSizePolicy.Expanding,
            QSizePolicy.Minimum,
        )

        self.horizontalLayout_2.addItem(self.horizontalSpacer)

        self.verticalLayout_2.addLayout(self.horizontalLayout_2)

        self.verticalLayout.addWidget(self.filter)

        self.groupBox = QGroupBox(ChannelMenu)
        self.groupBox.setObjectName("groupBox")
        self.groupBox.setEnabled(True)
        self.groupBox.setFont(font_groupbox)
        self.groupBox.setAlignment(Qt.AlignLeading | Qt.AlignLeft | Qt.AlignVCenter)
        self.verticalLayout_3 = QVBoxLayout(self.groupBox)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_4 = QHBoxLayout()
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(15, -1, -1, -1)
        self.noRef = QRadioButton(self.groupBox)
        self.noRef.setObjectName("noRef")
        self.noRef.setFont(font_standard)
        self.noRef.setChecked(True)
        self.noRef.setStyleSheet(radiobutton_style)

        self.horizontalLayout_4.addWidget(self.noRef)

        self.channelA = QRadioButton(self.groupBox)
        self.channelA.setObjectName("channelA")
        self.channelA.setFont(font_standard)
        self.channelA.setChecked(False)
        self.channelA.setStyleSheet(radiobutton_style)

        self.horizontalLayout_4.addWidget(self.channelA)

        self.channelB = QRadioButton(self.groupBox)
        self.channelB.setObjectName("channelB")
        self.channelB.setFont(font_standard)
        self.channelB.setStyleSheet(radiobutton_style)

        self.horizontalLayout_4.addWidget(self.channelB)

        self.channelC = QRadioButton(self.groupBox)
        self.channelC.setObjectName("channelC")
        self.channelC.setFont(font_standard)
        self.channelC.setStyleSheet(radiobutton_style)

        self.horizontalLayout_4.addWidget(self.channelC)

        self.channelD = QRadioButton(self.groupBox)
        self.channelD.setObjectName("channelD")
        self.channelD.setFont(font_standard)
        self.channelD.setStyleSheet(radiobutton_style)
        self.channelD.setChecked(False)

        self.horizontalLayout_4.addWidget(self.channelD)

        self.verticalLayout_3.addLayout(self.horizontalLayout_4)

        self.verticalLayout.addWidget(self.groupBox)

        self.groupBox_3 = QGroupBox(ChannelMenu)
        self.groupBox_3.setObjectName("groupBox_3")
        self.groupBox_3.setEnabled(True)
        self.groupBox_3.setFont(font_groupbox)
        self.horizontalLayout_3 = QHBoxLayout(self.groupBox_3)
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_5 = QHBoxLayout()
        self.horizontalLayout_5.setObjectName("horizontalLayout_5")
        self.label_2 = QLabel(self.groupBox_3)
        self.label_2.setObjectName("label_2")
        self.label_2.setMinimumSize(QSize(150, 0))
        self.label_2.setMaximumSize(QSize(150, 16777215))
        self.label_2.setFont(font_standard)
        self.label_2.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_5.addWidget(self.label_2)

        self.unit_ru = QRadioButton(self.groupBox_3)
        self.unit_ru.setObjectName("unit_ru")
        self.unit_ru.setChecked(True)

        self.horizontalLayout_5.addWidget(self.unit_ru)

        self.unit_nm = QRadioButton(self.groupBox_3)
        self.unit_nm.setObjectName("unit_nm")
        self.unit_nm.setEnabled(True)
        self.unit_nm.setChecked(False)

        self.horizontalLayout_5.addWidget(self.unit_nm)

        self.horizontalLayout_3.addLayout(self.horizontalLayout_5)

        self.verticalLayout.addWidget(self.groupBox_3)

        self.groupBox_2 = QGroupBox(ChannelMenu)
        self.groupBox_2.setObjectName("groupBox_2")
        self.groupBox_2.setFont(font_groupbox)
        self.horizontalLayout_7 = QHBoxLayout(self.groupBox_2)
        self.horizontalLayout_7.setObjectName("horizontalLayout_7")
        self.reset_data = QPushButton(self.groupBox_2)
        self.reset_data.setObjectName("reset_data")

        self.horizontalLayout_7.addWidget(self.reset_data)

        self.export_data = QPushButton(self.groupBox_2)
        self.export_data.setObjectName("export_data")

        self.horizontalLayout_7.addWidget(self.export_data)

        self.verticalLayout.addWidget(self.groupBox_2)

        self.groupBox_4 = QGroupBox(ChannelMenu)
        self.groupBox_4.setObjectName("groupBox_4")
        self.groupBox_4.setFont(font_groupbox)
        self.horizontalLayout_8 = QHBoxLayout(self.groupBox_4)
        self.horizontalLayout_8.setObjectName("horizontalLayout_8")
        self.colorblind_mode = QCheckBox(self.groupBox_4)
        self.colorblind_mode.setObjectName("colorblind_mode")
        self.colorblind_mode.setChecked(False)
        self.colorblind_mode.setStyleSheet(checkbox_style)

        self.horizontalLayout_8.addWidget(self.colorblind_mode)

        self.verticalLayout.addWidget(self.groupBox_4)

        self.retranslateUi(ChannelMenu)

        QMetaObject.connectSlotsByName(ChannelMenu)

    # setupUi

    def retranslateUi(self, ChannelMenu):
        ChannelMenu.setWindowTitle(
            QCoreApplication.translate("ChannelMenu", "SPR Settings", None),
        )
        self.filter.setTitle(
            QCoreApplication.translate("ChannelMenu", "Data Filtering", None),
        )
        self.filt_en.setText(
            QCoreApplication.translate("ChannelMenu", "Enable Filter", None),
        )
        self.label_5.setText(
            QCoreApplication.translate("ChannelMenu", "Filter Window Size:", None),
        )
        self.filt_win.setText(QCoreApplication.translate("ChannelMenu", "3", None))
        self.groupBox.setTitle(
            QCoreApplication.translate("ChannelMenu", "Reference Channel", None),
        )
        self.noRef.setText(QCoreApplication.translate("ChannelMenu", "None", None))
        self.channelA.setText(QCoreApplication.translate("ChannelMenu", " A", None))
        self.channelB.setText(QCoreApplication.translate("ChannelMenu", "B", None))
        self.channelC.setText(QCoreApplication.translate("ChannelMenu", "C", None))
        self.channelD.setText(QCoreApplication.translate("ChannelMenu", "D", None))
        self.groupBox_3.setTitle(
            QCoreApplication.translate("ChannelMenu", "Units", None),
        )
        self.label_2.setText(
            QCoreApplication.translate("ChannelMenu", "Display Shifts:", None),
        )
        self.unit_ru.setText(QCoreApplication.translate("ChannelMenu", "RU", None))
        self.unit_nm.setText(QCoreApplication.translate("ChannelMenu", "nm", None))
        self.groupBox_2.setTitle(
            QCoreApplication.translate("ChannelMenu", "Live Data", None),
        )
        self.reset_data.setText(
            QCoreApplication.translate("ChannelMenu", "Reset", None),
        )
        self.export_data.setText(
            QCoreApplication.translate("ChannelMenu", "Export", None),
        )
        self.groupBox_4.setTitle(
            QCoreApplication.translate("ChannelMenu", "Accessibility", None),
        )
        self.colorblind_mode.setText(
            QCoreApplication.translate(
                "ChannelMenu",
                "Colorblind-Friendly Palette",
                None,
            ),
        )

    # retranslateUi
