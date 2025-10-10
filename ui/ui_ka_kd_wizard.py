################################################################################
## Form generated from reading UI file 'ka_kd_wizard.ui'
##
## Created by: Qt User Interface Compiler version 6.6.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from pyqtgraph import PlotWidget
from PySide6.QtCore import QCoreApplication, QMetaObject, QSize, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpacerItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class Ui_KAKDWizardDialog:
    def setupUi(self, KAKDWizardDialog):
        if not KAKDWizardDialog.objectName():
            KAKDWizardDialog.setObjectName("KAKDWizardDialog")
        KAKDWizardDialog.resize(1050, 550)
        KAKDWizardDialog.setMinimumSize(QSize(1050, 550))
        font = QFont()
        font.setFamilies(["Segoe UI"])
        KAKDWizardDialog.setFont(font)
        self.verticalLayout = QVBoxLayout(KAKDWizardDialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout_4 = QHBoxLayout()
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        self.graph = PlotWidget(KAKDWizardDialog)
        self.graph.setObjectName("graph")
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.graph.sizePolicy().hasHeightForWidth())
        self.graph.setSizePolicy(sizePolicy)
        self.graph.setMinimumSize(QSize(600, 200))
        self.horizontalLayout = QHBoxLayout(self.graph)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.horizontalSpacer = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout.addItem(self.horizontalSpacer)

        self.verticalLayout_2 = QVBoxLayout()
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.label_cur_info = QLabel(self.graph)
        self.label_cur_info.setObjectName("label_cur_info")
        sizePolicy1 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(
            self.label_cur_info.sizePolicy().hasHeightForWidth()
        )
        self.label_cur_info.setSizePolicy(sizePolicy1)
        font1 = QFont()
        font1.setPointSize(8)
        self.label_cur_info.setFont(font1)
        self.label_cur_info.setStyleSheet("color: rgb(150, 150, 150);")
        self.label_cur_info.setAlignment(Qt.AlignRight | Qt.AlignTop | Qt.AlignTrailing)

        self.verticalLayout_2.addWidget(self.label_cur_info)

        self.verticalSpacer = QSpacerItem(
            20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding
        )

        self.verticalLayout_2.addItem(self.verticalSpacer)

        self.horizontalLayout.addLayout(self.verticalLayout_2)

        self.horizontalLayout_4.addWidget(self.graph)

        self.table = QTableWidget(KAKDWizardDialog)
        if self.table.columnCount() < 4:
            self.table.setColumnCount(4)
        font2 = QFont()
        font2.setPointSize(9)
        __qtablewidgetitem = QTableWidgetItem()
        __qtablewidgetitem.setTextAlignment(Qt.AlignCenter)
        __qtablewidgetitem.setFont(font2)
        self.table.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        __qtablewidgetitem1.setTextAlignment(Qt.AlignCenter)
        __qtablewidgetitem1.setFont(font2)
        self.table.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        __qtablewidgetitem2.setTextAlignment(Qt.AlignCenter)
        __qtablewidgetitem2.setFont(font2)
        self.table.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        __qtablewidgetitem3.setTextAlignment(Qt.AlignCenter)
        self.table.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        self.table.setObjectName("table")
        self.table.setMinimumSize(QSize(410, 0))
        self.table.setMaximumSize(QSize(410, 16777215))
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setMinimumSectionSize(100)
        self.table.horizontalHeader().setDefaultSectionSize(100)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)

        self.horizontalLayout_4.addWidget(self.table)

        self.verticalLayout.addLayout(self.horizontalLayout_4)

        self.frame_2 = QFrame(KAKDWizardDialog)
        self.frame_2.setObjectName("frame_2")
        self.frame_2.setMinimumSize(QSize(0, 100))
        self.frame_2.setMaximumSize(QSize(16777215, 100))
        self.frame_2.setFrameShape(QFrame.StyledPanel)
        self.frame_2.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_5 = QHBoxLayout(self.frame_2)
        self.horizontalLayout_5.setObjectName("horizontalLayout_5")
        self.groupBox_2 = QGroupBox(self.frame_2)
        self.groupBox_2.setObjectName("groupBox_2")
        self.groupBox_2.setMinimumSize(QSize(200, 70))
        self.groupBox_2.setMaximumSize(QSize(220, 70))
        self.groupBox_2.setFont(font2)
        self.horizontalLayout_3 = QHBoxLayout(self.groupBox_2)
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(-1, 7, -1, 11)
        self.ch_a = QRadioButton(self.groupBox_2)
        self.ch_a.setObjectName("ch_a")
        self.ch_a.setChecked(True)

        self.horizontalLayout_3.addWidget(self.ch_a, 0, Qt.AlignTop)

        self.ch_b = QRadioButton(self.groupBox_2)
        self.ch_b.setObjectName("ch_b")

        self.horizontalLayout_3.addWidget(self.ch_b, 0, Qt.AlignTop)

        self.ch_c = QRadioButton(self.groupBox_2)
        self.ch_c.setObjectName("ch_c")

        self.horizontalLayout_3.addWidget(self.ch_c, 0, Qt.AlignTop)

        self.ch_d = QRadioButton(self.groupBox_2)
        self.ch_d.setObjectName("ch_d")

        self.horizontalLayout_3.addWidget(self.ch_d, 0, Qt.AlignTop)

        self.horizontalLayout_5.addWidget(self.groupBox_2)

        self.affinity_result = QGroupBox(self.frame_2)
        self.affinity_result.setObjectName("affinity_result")
        sizePolicy.setHeightForWidth(
            self.affinity_result.sizePolicy().hasHeightForWidth()
        )
        self.affinity_result.setSizePolicy(sizePolicy)
        self.affinity_result.setMinimumSize(QSize(360, 70))
        self.affinity_result.setMaximumSize(QSize(10000, 70))
        font3 = QFont()
        font3.setPointSize(9)
        font3.setBold(False)
        self.affinity_result.setFont(font3)
        self.layout_constant = QHBoxLayout(self.affinity_result)
        self.layout_constant.setSpacing(10)
        self.layout_constant.setObjectName("layout_constant")
        self.layout_constant.setContentsMargins(-1, 7, -1, -1)
        self.label = QLabel(self.affinity_result)
        self.label.setObjectName("label")
        self.label.setMinimumSize(QSize(30, 0))
        font4 = QFont()
        font4.setBold(False)
        self.label.setFont(font4)
        self.label.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)

        self.layout_constant.addWidget(self.label, 0, Qt.AlignRight)

        self.lb_KD = QLabel(self.affinity_result)
        self.lb_KD.setObjectName("lb_KD")
        sizePolicy.setHeightForWidth(self.lb_KD.sizePolicy().hasHeightForWidth())
        self.lb_KD.setSizePolicy(sizePolicy)
        self.lb_KD.setMinimumSize(QSize(70, 0))

        self.layout_constant.addWidget(self.lb_KD)

        self.label_2 = QLabel(self.affinity_result)
        self.label_2.setObjectName("label_2")
        self.label_2.setMinimumSize(QSize(40, 0))
        self.label_2.setFont(font4)
        self.label_2.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)

        self.layout_constant.addWidget(self.label_2, 0, Qt.AlignRight)

        self.lb_Rmax = QLabel(self.affinity_result)
        self.lb_Rmax.setObjectName("lb_Rmax")
        sizePolicy.setHeightForWidth(self.lb_Rmax.sizePolicy().hasHeightForWidth())
        self.lb_Rmax.setSizePolicy(sizePolicy)
        self.lb_Rmax.setMinimumSize(QSize(70, 0))

        self.layout_constant.addWidget(self.lb_Rmax)

        self.label_4 = QLabel(self.affinity_result)
        self.label_4.setObjectName("label_4")
        self.label_4.setMinimumSize(QSize(30, 0))
        self.label_4.setFont(font4)
        self.label_4.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)

        self.layout_constant.addWidget(self.label_4)

        self.lb_ka = QLabel(self.affinity_result)
        self.lb_ka.setObjectName("lb_ka")
        sizePolicy.setHeightForWidth(self.lb_ka.sizePolicy().hasHeightForWidth())
        self.lb_ka.setSizePolicy(sizePolicy)
        self.lb_ka.setMinimumSize(QSize(70, 0))

        self.layout_constant.addWidget(self.lb_ka)

        self.label_3 = QLabel(self.affinity_result)
        self.label_3.setObjectName("label_3")
        self.label_3.setMinimumSize(QSize(30, 0))
        self.label_3.setFont(font4)
        self.label_3.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)

        self.layout_constant.addWidget(self.label_3)

        self.lb_kd = QLabel(self.affinity_result)
        self.lb_kd.setObjectName("lb_kd")
        sizePolicy.setHeightForWidth(self.lb_kd.sizePolicy().hasHeightForWidth())
        self.lb_kd.setSizePolicy(sizePolicy)
        self.lb_kd.setMinimumSize(QSize(70, 0))

        self.layout_constant.addWidget(self.lb_kd)

        self.label_5 = QLabel(self.affinity_result)
        self.label_5.setObjectName("label_5")
        self.label_5.setMinimumSize(QSize(30, 0))
        self.label_5.setFont(font4)
        self.label_5.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)

        self.layout_constant.addWidget(self.label_5)

        self.lb_r_sq = QLabel(self.affinity_result)
        self.lb_r_sq.setObjectName("lb_r_sq")
        sizePolicy.setHeightForWidth(self.lb_r_sq.sizePolicy().hasHeightForWidth())
        self.lb_r_sq.setSizePolicy(sizePolicy)
        self.lb_r_sq.setMinimumSize(QSize(60, 0))

        self.layout_constant.addWidget(self.lb_r_sq)

        self.horizontalLayout_5.addWidget(self.affinity_result)

        self.frame = QFrame(self.frame_2)
        self.frame.setObjectName("frame")
        self.frame.setFont(font2)
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_2 = QHBoxLayout(self.frame)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.horizontalSpacer_2 = QSpacerItem(
            20, 20, QSizePolicy.Fixed, QSizePolicy.Minimum
        )

        self.horizontalLayout_2.addItem(self.horizontalSpacer_2)

        self.btn_kd = QPushButton(self.frame)
        self.btn_kd.setObjectName("btn_kd")
        sizePolicy1.setHeightForWidth(self.btn_kd.sizePolicy().hasHeightForWidth())
        self.btn_kd.setSizePolicy(sizePolicy1)
        self.btn_kd.setMinimumSize(QSize(100, 40))
        self.btn_kd.setMaximumSize(QSize(100, 40))
        font5 = QFont()
        font5.setFamilies(["Segoe UI"])
        font5.setPointSize(8)
        self.btn_kd.setFont(font5)
        self.btn_kd.setStyleSheet(
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

        self.horizontalLayout_2.addWidget(self.btn_kd)

        self.horizontalSpacer_3 = QSpacerItem(
            20, 20, QSizePolicy.Fixed, QSizePolicy.Minimum
        )

        self.horizontalLayout_2.addItem(self.horizontalSpacer_3)

        self.btn_save = QPushButton(self.frame)
        self.btn_save.setObjectName("btn_save")
        sizePolicy2 = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.btn_save.sizePolicy().hasHeightForWidth())
        self.btn_save.setSizePolicy(sizePolicy2)
        self.btn_save.setMinimumSize(QSize(30, 30))
        self.btn_save.setMaximumSize(QSize(30, 30))
        font6 = QFont()
        font6.setPointSize(5)
        self.btn_save.setFont(font6)
        self.btn_save.setMouseTracking(True)
        self.btn_save.setLayoutDirection(Qt.LeftToRight)
        self.btn_save.setAutoFillBackground(False)
        self.btn_save.setStyleSheet(
            "QPushButton{\n"
            "	border: none;\n"
            "	background: none;\n"
            "}\n"
            "\n"
            "QPushButton::hover{\n"
            "	background: white;\n"
            "	border: 1px raised;\n"
            "	border-radius: 10px;\n"
            "}"
        )
        icon = QIcon()
        icon.addFile(":/img/img/save.png", QSize(), QIcon.Normal, QIcon.Off)
        self.btn_save.setIcon(icon)
        self.btn_save.setIconSize(QSize(30, 30))
        self.btn_save.setAutoRepeat(False)
        self.btn_save.setAutoExclusive(False)
        self.btn_save.setAutoDefault(False)
        self.btn_save.setFlat(False)

        self.horizontalLayout_2.addWidget(self.btn_save)

        self.horizontalLayout_5.addWidget(self.frame)

        self.verticalLayout.addWidget(self.frame_2)

        self.retranslateUi(KAKDWizardDialog)

        self.btn_save.setDefault(False)

        QMetaObject.connectSlotsByName(KAKDWizardDialog)

    # setupUi

    def retranslateUi(self, KAKDWizardDialog):
        KAKDWizardDialog.setWindowTitle(
            QCoreApplication.translate("KAKDWizardDialog", "Kinetic Wizard", None)
        )
        self.label_cur_info.setText("")
        ___qtablewidgetitem = self.table.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(
            QCoreApplication.translate("KAKDWizardDialog", "Cycle", None)
        )
        ___qtablewidgetitem1 = self.table.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(
            QCoreApplication.translate("KAKDWizardDialog", "Conc'n (nM)", None)
        )
        ___qtablewidgetitem2 = self.table.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(
            QCoreApplication.translate(
                "KAKDWizardDialog", "Association\nShift (RU)", None
            )
        )
        ___qtablewidgetitem3 = self.table.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(
            QCoreApplication.translate(
                "KAKDWizardDialog", "Dissociation\nShift (RU)", None
            )
        )
        self.groupBox_2.setTitle(
            QCoreApplication.translate("KAKDWizardDialog", "Channel", None)
        )
        self.ch_a.setText(QCoreApplication.translate("KAKDWizardDialog", "A", None))
        self.ch_b.setText(QCoreApplication.translate("KAKDWizardDialog", "B", None))
        self.ch_c.setText(QCoreApplication.translate("KAKDWizardDialog", "C", None))
        self.ch_d.setText(QCoreApplication.translate("KAKDWizardDialog", "D", None))
        self.affinity_result.setTitle(
            QCoreApplication.translate("KAKDWizardDialog", "Results", None)
        )
        self.label.setText(QCoreApplication.translate("KAKDWizardDialog", "KD:", None))
        self.lb_KD.setText("")
        self.label_2.setText(
            QCoreApplication.translate(
                "KAKDWizardDialog",
                '<html><head/><body><p>R<span style=" vertical-align:sub;">MAX</span>:</p></body></html>',
                None,
            )
        )
        self.lb_Rmax.setText("")
        self.label_4.setText(
            QCoreApplication.translate(
                "KAKDWizardDialog", "<html><head/><body><p>ka:</p></body></html>", None
            )
        )
        self.lb_ka.setText("")
        self.label_3.setText(
            QCoreApplication.translate("KAKDWizardDialog", "kd:", None)
        )
        self.lb_kd.setText("")
        self.label_5.setText(
            QCoreApplication.translate(
                "KAKDWizardDialog",
                '<html><head/><body><p>R<span style=" vertical-align:super;">2</span>:</p></body></html>',
                None,
            )
        )
        self.lb_r_sq.setText("")
        self.btn_kd.setText(
            QCoreApplication.translate("KAKDWizardDialog", "Calculate\nResults", None)
        )
        # if QT_CONFIG(tooltip)
        self.btn_save.setToolTip(
            QCoreApplication.translate("KAKDWizardDialog", "Export Segment Data", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.btn_save.setText("")

    # retranslateUi
