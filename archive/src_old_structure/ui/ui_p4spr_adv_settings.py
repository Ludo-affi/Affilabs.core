# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'p4spr_adv_settings.ui'
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
from PySide6.QtWidgets import (QApplication, QFormLayout, QFrame, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget)
import ui.ai_rc

class Ui_P4SPR_Advanced(object):
    def setupUi(self, P4SPR_Advanced):
        if not P4SPR_Advanced.objectName():
            P4SPR_Advanced.setObjectName(u"P4SPR_Advanced")
        P4SPR_Advanced.resize(321, 640)
        P4SPR_Advanced.setFocusPolicy(Qt.StrongFocus)
        icon = QIcon()
        icon.addFile(u":/img/img/affinite2.ico", QSize(), QIcon.Normal, QIcon.Off)
        P4SPR_Advanced.setWindowIcon(icon)
        self.verticalLayout = QVBoxLayout(P4SPR_Advanced)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.label = QLabel(P4SPR_Advanced)
        self.label.setObjectName(u"label")
        font = QFont()
        font.setFamilies([u"Segoe UI"])
        font.setPointSize(9)
        font.setBold(True)
        self.label.setFont(font)
        self.label.setAlignment(Qt.AlignHCenter|Qt.AlignTop)
        self.label.setMargin(10)

        self.verticalLayout.addWidget(self.label)

        # Standard font for groupbox titles
        font_groupbox = QFont()
        font_groupbox.setFamilies([u"Segoe UI"])
        font_groupbox.setPointSize(8)

        self.groupBox_4 = QGroupBox(P4SPR_Advanced)
        self.groupBox_4.setObjectName(u"groupBox_4")
        self.groupBox_4.setFont(font_groupbox)
        self.formLayout = QFormLayout(self.groupBox_4)
        self.formLayout.setObjectName(u"formLayout")
        self.label_8 = QLabel(self.groupBox_4)
        self.label_8.setObjectName(u"label_8")

        self.formLayout.setWidget(0, QFormLayout.LabelRole, self.label_8)

        self.intg_time = QLineEdit(self.groupBox_4)
        self.intg_time.setObjectName(u"intg_time")

        self.formLayout.setWidget(0, QFormLayout.FieldRole, self.intg_time)

        self.label_2 = QLabel(self.groupBox_4)
        self.label_2.setObjectName(u"label_2")

        self.formLayout.setWidget(1, QFormLayout.LabelRole, self.label_2)

        self.num_scans = QLineEdit(self.groupBox_4)
        self.num_scans.setObjectName(u"num_scans")

        self.formLayout.setWidget(1, QFormLayout.FieldRole, self.num_scans)

        self.label_7 = QLabel(self.groupBox_4)
        self.label_7.setObjectName(u"label_7")

        self.formLayout.setWidget(2, QFormLayout.LabelRole, self.label_7)

        self.led_int_a = QLineEdit(self.groupBox_4)
        self.led_int_a.setObjectName(u"led_int_a")

        self.formLayout.setWidget(2, QFormLayout.FieldRole, self.led_int_a)

        self.label_9 = QLabel(self.groupBox_4)
        self.label_9.setObjectName(u"label_9")

        self.formLayout.setWidget(3, QFormLayout.LabelRole, self.label_9)

        self.led_int_b = QLineEdit(self.groupBox_4)
        self.led_int_b.setObjectName(u"led_int_b")

        self.formLayout.setWidget(3, QFormLayout.FieldRole, self.led_int_b)

        self.label_10 = QLabel(self.groupBox_4)
        self.label_10.setObjectName(u"label_10")

        self.formLayout.setWidget(4, QFormLayout.LabelRole, self.label_10)

        self.led_int_c = QLineEdit(self.groupBox_4)
        self.led_int_c.setObjectName(u"led_int_c")

        self.formLayout.setWidget(4, QFormLayout.FieldRole, self.led_int_c)

        self.label_11 = QLabel(self.groupBox_4)
        self.label_11.setObjectName(u"label_11")

        self.formLayout.setWidget(5, QFormLayout.LabelRole, self.label_11)

        self.led_int_d = QLineEdit(self.groupBox_4)
        self.led_int_d.setObjectName(u"led_int_d")

        self.formLayout.setWidget(5, QFormLayout.FieldRole, self.led_int_d)


        self.verticalLayout.addWidget(self.groupBox_4)

        self.groupBox_3 = QGroupBox(P4SPR_Advanced)
        self.groupBox_3.setObjectName(u"groupBox_3")
        self.groupBox_3.setFont(font_groupbox)
        self.formLayout_3 = QFormLayout(self.groupBox_3)
        self.formLayout_3.setObjectName(u"formLayout_3")
        self.label_12 = QLabel(self.groupBox_3)
        self.label_12.setObjectName(u"label_12")
        self.label_12.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignVCenter)

        self.formLayout_3.setWidget(0, QFormLayout.LabelRole, self.label_12)

        self.s_pos = QLineEdit(self.groupBox_3)
        self.s_pos.setObjectName(u"s_pos")

        self.formLayout_3.setWidget(0, QFormLayout.FieldRole, self.s_pos)

        self.label_13 = QLabel(self.groupBox_3)
        self.label_13.setObjectName(u"label_13")
        self.label_13.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignVCenter)

        self.formLayout_3.setWidget(1, QFormLayout.LabelRole, self.label_13)

        self.p_pos = QLineEdit(self.groupBox_3)
        self.p_pos.setObjectName(u"p_pos")

        self.formLayout_3.setWidget(1, QFormLayout.FieldRole, self.p_pos)


        self.verticalLayout.addWidget(self.groupBox_3)

        self.groupBox = QGroupBox(P4SPR_Advanced)
        self.groupBox.setObjectName(u"groupBox")
        self.groupBox.setFont(font_groupbox)
        self.formLayout_4 = QFormLayout(self.groupBox)
        self.formLayout_4.setObjectName(u"formLayout_4")
        self.pump_1_correction = QLineEdit(self.groupBox)
        self.pump_1_correction.setObjectName(u"pump_1_correction")

        self.formLayout_4.setWidget(0, QFormLayout.FieldRole, self.pump_1_correction)

        self.label_14 = QLabel(self.groupBox)
        self.label_14.setObjectName(u"label_14")

        self.formLayout_4.setWidget(0, QFormLayout.LabelRole, self.label_14)

        self.label_15 = QLabel(self.groupBox)
        self.label_15.setObjectName(u"label_15")

        self.formLayout_4.setWidget(1, QFormLayout.LabelRole, self.label_15)

        self.pump_2_correction = QLineEdit(self.groupBox)
        self.pump_2_correction.setObjectName(u"pump_2_correction")

        self.formLayout_4.setWidget(1, QFormLayout.FieldRole, self.pump_2_correction)


        self.verticalLayout.addWidget(self.groupBox)

        self.groupBox_2 = QGroupBox(P4SPR_Advanced)
        self.groupBox_2.setObjectName(u"groupBox_2")
        self.groupBox_2.setFont(font_groupbox)
        self.formLayout_2 = QFormLayout(self.groupBox_2)
        self.formLayout_2.setObjectName(u"formLayout_2")
        self.label_4 = QLabel(self.groupBox_2)
        self.label_4.setObjectName(u"label_4")

        self.formLayout_2.setWidget(0, QFormLayout.LabelRole, self.label_4)

        self.led_del = QLineEdit(self.groupBox_2)
        self.led_del.setObjectName(u"led_del")

        self.formLayout_2.setWidget(0, QFormLayout.FieldRole, self.led_del)

        self.label_3 = QLabel(self.groupBox_2)
        self.label_3.setObjectName(u"label_3")

        self.formLayout_2.setWidget(1, QFormLayout.LabelRole, self.label_3)

        self.ht_req = QLineEdit(self.groupBox_2)
        self.ht_req.setObjectName(u"ht_req")

        self.formLayout_2.setWidget(1, QFormLayout.FieldRole, self.ht_req)

        self.label_6 = QLabel(self.groupBox_2)
        self.label_6.setObjectName(u"label_6")

        self.formLayout_2.setWidget(2, QFormLayout.LabelRole, self.label_6)

        self.sens_interval = QLineEdit(self.groupBox_2)
        self.sens_interval.setObjectName(u"sens_interval")

        self.formLayout_2.setWidget(2, QFormLayout.FieldRole, self.sens_interval)

        self.label_5 = QLabel(self.groupBox_2)
        self.label_5.setObjectName(u"label_5")

        self.formLayout_2.setWidget(3, QFormLayout.LabelRole, self.label_5)

        self.contact_time = QLineEdit(self.groupBox_2)
        self.contact_time.setObjectName(u"contact_time")

        self.formLayout_2.setWidget(3, QFormLayout.FieldRole, self.contact_time)


        self.verticalLayout.addWidget(self.groupBox_2)

        self.frame = QFrame(P4SPR_Advanced)
        self.frame.setObjectName(u"frame")
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout = QHBoxLayout(self.frame)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.set_btn = QPushButton(self.frame)
        self.set_btn.setObjectName(u"set_btn")

        self.horizontalLayout.addWidget(self.set_btn)


        self.verticalLayout.addWidget(self.frame)


        self.retranslateUi(P4SPR_Advanced)

        QMetaObject.connectSlotsByName(P4SPR_Advanced)
    # setupUi

    def retranslateUi(self, P4SPR_Advanced):
        P4SPR_Advanced.setWindowTitle(QCoreApplication.translate("P4SPR_Advanced", u"Advanced Settings", None))
        self.label.setText(QCoreApplication.translate("P4SPR_Advanced", u"Advanced Parameter Settings", None))
        self.groupBox_4.setTitle(QCoreApplication.translate("P4SPR_Advanced", u"LED && Detector Settings", None))
        self.label_8.setText(QCoreApplication.translate("P4SPR_Advanced", u"Integration Time (ms)", None))
        self.label_2.setText(QCoreApplication.translate("P4SPR_Advanced", u"Number of Scans", None))
        self.label_7.setText(QCoreApplication.translate("P4SPR_Advanced", u"LED A Intensity (1-255)", None))
        self.label_9.setText(QCoreApplication.translate("P4SPR_Advanced", u"LED B Intensity (1-255)", None))
        self.label_10.setText(QCoreApplication.translate("P4SPR_Advanced", u"LED C Intensity (1-255)", None))
        self.label_11.setText(QCoreApplication.translate("P4SPR_Advanced", u"LED D Intensity (1-255)", None))
        self.groupBox_3.setTitle(QCoreApplication.translate("P4SPR_Advanced", u"Polarizer", None))
        self.label_12.setText(QCoreApplication.translate("P4SPR_Advanced", u"S Position (deg)", None))
        self.label_13.setText(QCoreApplication.translate("P4SPR_Advanced", u"P Position (deg)", None))
        self.groupBox.setTitle(QCoreApplication.translate("P4SPR_Advanced", u"Peristaltic Pumps", None))
        self.label_14.setText(QCoreApplication.translate("P4SPR_Advanced", u"Pump 1 Correction", None))
        self.label_15.setText(QCoreApplication.translate("P4SPR_Advanced", u"Pump 2 Correction", None))
        self.groupBox_2.setTitle(QCoreApplication.translate("P4SPR_Advanced", u"Development Use Only", None))
        self.label_4.setText(QCoreApplication.translate("P4SPR_Advanced", u"LED Delay (sec)", None))
        self.label_3.setText(QCoreApplication.translate("P4SPR_Advanced", u"%T Height Req. (factor)", None))
        self.label_6.setText(QCoreApplication.translate("P4SPR_Advanced", u"Kinetic Sensor Interval (sec)", None))
        self.label_5.setText(QCoreApplication.translate("P4SPR_Advanced", u"Regenerate time (sec)", None))
        self.contact_time.setText(QCoreApplication.translate("P4SPR_Advanced", u"13", None))
        self.set_btn.setText(QCoreApplication.translate("P4SPR_Advanced", u"Update Settings", None))
    # retranslateUi

