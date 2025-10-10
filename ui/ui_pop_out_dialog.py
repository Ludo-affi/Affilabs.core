################################################################################
## Form generated from reading UI file 'pop_out_dialog.ui'
##
## Created by: Qt User Interface Compiler version 6.6.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import QCoreApplication, QMetaObject, QSize, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QFrame, QSizePolicy, QVBoxLayout


class Ui_SingleDialog:
    def setupUi(self, SingleDialog):
        if not SingleDialog.objectName():
            SingleDialog.setObjectName("SingleDialog")
        SingleDialog.resize(1026, 656)
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(SingleDialog.sizePolicy().hasHeightForWidth())
        SingleDialog.setSizePolicy(sizePolicy)
        SingleDialog.setMinimumSize(QSize(0, 0))
        SingleDialog.setMaximumSize(QSize(10000, 10000))
        font = QFont()
        font.setFamilies(["Segoe UI"])
        SingleDialog.setFont(font)
        SingleDialog.setFocusPolicy(Qt.StrongFocus)
        icon = QIcon()
        icon.addFile(":/img/img/affinite2.ico", QSize(), QIcon.Normal, QIcon.Off)
        SingleDialog.setWindowIcon(icon)
        SingleDialog.setStyleSheet("")
        self.verticalLayout = QVBoxLayout(SingleDialog)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName("verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.single_frame = QFrame(SingleDialog)
        self.single_frame.setObjectName("single_frame")
        sizePolicy1 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(
            self.single_frame.sizePolicy().hasHeightForWidth()
        )
        self.single_frame.setSizePolicy(sizePolicy1)
        self.single_frame.setFrameShape(QFrame.StyledPanel)
        self.single_frame.setFrameShadow(QFrame.Raised)

        self.verticalLayout.addWidget(self.single_frame)

        self.retranslateUi(SingleDialog)

        QMetaObject.connectSlotsByName(SingleDialog)

    # setupUi

    def retranslateUi(self, SingleDialog):
        SingleDialog.setWindowTitle(
            QCoreApplication.translate("SingleDialog", "Advanced Spectroscopy", None)
        )

    # retranslateUi
