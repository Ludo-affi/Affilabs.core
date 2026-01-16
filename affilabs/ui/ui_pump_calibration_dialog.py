# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'pump_calibration_dialog.ui'
##
## Created by: Qt User Interface Compiler version 6.4.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPainter, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QAbstractButton, QApplication, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel,
    QPushButton, QSizePolicy, QSpacerItem, QVBoxLayout,
    QWidget)

class Ui_PumpCalibrationDialog(object):
    def setupUi(self, PumpCalibrationDialog):
        if not PumpCalibrationDialog.objectName():
            PumpCalibrationDialog.setObjectName(u"PumpCalibrationDialog")
        PumpCalibrationDialog.resize(400, 280)
        PumpCalibrationDialog.setModal(True)
        self.verticalLayout = QVBoxLayout(PumpCalibrationDialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.label_title = QLabel(PumpCalibrationDialog)
        self.label_title.setObjectName(u"label_title")

        self.verticalLayout.addWidget(self.label_title)

        self.label_description = QLabel(PumpCalibrationDialog)
        self.label_description.setObjectName(u"label_description")
        self.label_description.setWordWrap(True)

        self.verticalLayout.addWidget(self.label_description)

        self.verticalSpacer_1 = QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Fixed)

        self.verticalLayout.addItem(self.verticalSpacer_1)

        self.formLayout = QFormLayout()
        self.formLayout.setObjectName(u"formLayout")
        self.label_pump1 = QLabel(PumpCalibrationDialog)
        self.label_pump1.setObjectName(u"label_pump1")

        self.formLayout.setWidget(0, QFormLayout.LabelRole, self.label_pump1)

        self.horizontalLayout_pump1 = QHBoxLayout()
        self.horizontalLayout_pump1.setObjectName(u"horizontalLayout_pump1")
        self.pump1_spinbox = QDoubleSpinBox(PumpCalibrationDialog)
        self.pump1_spinbox.setObjectName(u"pump1_spinbox")
        self.pump1_spinbox.setDecimals(3)
        self.pump1_spinbox.setMinimum(0.500000000000000)
        self.pump1_spinbox.setMaximum(2.000000000000000)
        self.pump1_spinbox.setSingleStep(0.010000000000000)
        self.pump1_spinbox.setValue(1.000000000000000)

        self.horizontalLayout_pump1.addWidget(self.pump1_spinbox)

        self.pump1_reset_btn = QPushButton(PumpCalibrationDialog)
        self.pump1_reset_btn.setObjectName(u"pump1_reset_btn")
        self.pump1_reset_btn.setMaximumSize(QSize(60, 16777215))

        self.horizontalLayout_pump1.addWidget(self.pump1_reset_btn)


        self.formLayout.setLayout(0, QFormLayout.FieldRole, self.horizontalLayout_pump1)

        self.label_pump2 = QLabel(PumpCalibrationDialog)
        self.label_pump2.setObjectName(u"label_pump2")

        self.formLayout.setWidget(1, QFormLayout.LabelRole, self.label_pump2)

        self.horizontalLayout_pump2 = QHBoxLayout()
        self.horizontalLayout_pump2.setObjectName(u"horizontalLayout_pump2")
        self.pump2_spinbox = QDoubleSpinBox(PumpCalibrationDialog)
        self.pump2_spinbox.setObjectName(u"pump2_spinbox")
        self.pump2_spinbox.setDecimals(3)
        self.pump2_spinbox.setMinimum(0.500000000000000)
        self.pump2_spinbox.setMaximum(2.000000000000000)
        self.pump2_spinbox.setSingleStep(0.010000000000000)
        self.pump2_spinbox.setValue(1.000000000000000)

        self.horizontalLayout_pump2.addWidget(self.pump2_spinbox)

        self.pump2_reset_btn = QPushButton(PumpCalibrationDialog)
        self.pump2_reset_btn.setObjectName(u"pump2_reset_btn")
        self.pump2_reset_btn.setMaximumSize(QSize(60, 16777215))

        self.horizontalLayout_pump2.addWidget(self.pump2_reset_btn)


        self.formLayout.setLayout(1, QFormLayout.FieldRole, self.horizontalLayout_pump2)


        self.verticalLayout.addLayout(self.formLayout)

        self.verticalSpacer_2 = QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Fixed)

        self.verticalLayout.addItem(self.verticalSpacer_2)

        self.label_info = QLabel(PumpCalibrationDialog)
        self.label_info.setObjectName(u"label_info")
        self.label_info.setWordWrap(True)

        self.verticalLayout.addWidget(self.label_info)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer)

        self.buttonBox = QDialogButtonBox(PumpCalibrationDialog)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Apply|QDialogButtonBox.Cancel|QDialogButtonBox.Ok)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(PumpCalibrationDialog)
        self.buttonBox.accepted.connect(PumpCalibrationDialog.accept)
        self.buttonBox.rejected.connect(PumpCalibrationDialog.reject)

        QMetaObject.connectSlotsByName(PumpCalibrationDialog)
    # setupUi

    def retranslateUi(self, PumpCalibrationDialog):
        PumpCalibrationDialog.setWindowTitle(QCoreApplication.translate("PumpCalibrationDialog", u"Internal Pump Calibration", None))
        self.label_title.setText(QCoreApplication.translate("PumpCalibrationDialog", u"<html><head/><body><p><span style=\" font-size:10pt; font-weight:600;\">Pump Speed Calibration</span></p></body></html>", None))
        self.label_description.setText(QCoreApplication.translate("PumpCalibrationDialog", u"Adjust pump correction factors to match flow rates. \n"
"Values > 1.0 increase speed, < 1.0 decrease speed.", None))
        self.label_pump1.setText(QCoreApplication.translate("PumpCalibrationDialog", u"Pump KC1 Correction:", None))
        self.pump1_reset_btn.setText(QCoreApplication.translate("PumpCalibrationDialog", u"Reset", None))
        self.label_pump2.setText(QCoreApplication.translate("PumpCalibrationDialog", u"Pump KC2 Correction:", None))
        self.pump2_reset_btn.setText(QCoreApplication.translate("PumpCalibrationDialog", u"Reset", None))
        self.label_info.setText(QCoreApplication.translate("PumpCalibrationDialog", u"<html><head/><body><p><span style=\" font-style:italic;\">Example: If KC1 pumps 10% slower than KC2, set KC1 = 1.100</span></p></body></html>", None))
    # retranslateUi

