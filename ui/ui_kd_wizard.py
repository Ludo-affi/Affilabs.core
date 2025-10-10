################################################################################
## Form generated from reading UI file 'kd_wizard.ui'
##
## Created by: Qt User Interface Compiler version 6.6.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from pyqtgraph import PlotWidget
from PySide6.QtCore import QCoreApplication, QMetaObject, QRect, QSize, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
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


class Ui_KDWizardDialog:
    def setupUi(self, KDWizardDialog):
        if not KDWizardDialog.objectName():
            KDWizardDialog.setObjectName("KDWizardDialog")
        KDWizardDialog.resize(1050, 500)
        KDWizardDialog.setMinimumSize(QSize(1050, 500))
        font = QFont()
        font.setFamilies(["Segoe UI"])
        KDWizardDialog.setFont(font)
        self.verticalLayout = QVBoxLayout(KDWizardDialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout_4 = QHBoxLayout()
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        self.graph = PlotWidget(KDWizardDialog)
        self.graph.setObjectName("graph")
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
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(
            self.label_cur_info.sizePolicy().hasHeightForWidth()
        )
        self.label_cur_info.setSizePolicy(sizePolicy)
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

        self.verticalLayout_3 = QVBoxLayout()
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(10, -1, -1, -1)
        self.table = QTableWidget(KDWizardDialog)
        if self.table.columnCount() < 4:
            self.table.setColumnCount(4)
        font2 = QFont()
        font2.setFamilies(["Segoe UI"])
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
        __qtablewidgetitem3.setFont(font2)
        self.table.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        self.table.setObjectName("table")
        self.table.setMinimumSize(QSize(350, 0))
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setMinimumSectionSize(100)
        self.table.horizontalHeader().setDefaultSectionSize(100)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)

        self.verticalLayout_3.addWidget(self.table)

        self.horizontalLayout_9 = QHBoxLayout()
        self.horizontalLayout_9.setObjectName("horizontalLayout_9")
        self.horizontalLayout_9.setContentsMargins(5, 5, 5, 5)
        self.add_shifts = QCheckBox(KDWizardDialog)
        self.add_shifts.setObjectName("add_shifts")
        font3 = QFont()
        font3.setPointSize(9)
        font3.setBold(False)
        font3.setItalic(False)
        self.add_shifts.setFont(font3)

        self.horizontalLayout_9.addWidget(self.add_shifts, 0, Qt.AlignHCenter)

        self.horizontalSpacer_5 = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout_9.addItem(self.horizontalSpacer_5)

        self.btn_kd = QPushButton(KDWizardDialog)
        self.btn_kd.setObjectName("btn_kd")
        sizePolicy.setHeightForWidth(self.btn_kd.sizePolicy().hasHeightForWidth())
        self.btn_kd.setSizePolicy(sizePolicy)
        self.btn_kd.setMinimumSize(QSize(100, 30))
        self.btn_kd.setMaximumSize(QSize(100, 30))
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
        self.btn_kd.setAutoDefault(False)

        self.horizontalLayout_9.addWidget(self.btn_kd)

        self.verticalLayout_3.addLayout(self.horizontalLayout_9)

        self.horizontalLayout_4.addLayout(self.verticalLayout_3)

        self.verticalLayout.addLayout(self.horizontalLayout_4)

        self.frame_2 = QFrame(KDWizardDialog)
        self.frame_2.setObjectName("frame_2")
        self.frame_2.setMinimumSize(QSize(0, 100))
        self.frame_2.setMaximumSize(QSize(16777215, 100))
        self.frame_2.setFrameShape(QFrame.StyledPanel)
        self.frame_2.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_8 = QHBoxLayout(self.frame_2)
        self.horizontalLayout_8.setObjectName("horizontalLayout_8")
        self.groupBox_2 = QGroupBox(self.frame_2)
        self.groupBox_2.setObjectName("groupBox_2")
        self.groupBox_2.setMinimumSize(QSize(200, 70))
        self.groupBox_2.setMaximumSize(QSize(220, 70))
        font4 = QFont()
        font4.setPointSize(9)
        self.groupBox_2.setFont(font4)
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

        self.horizontalLayout_8.addWidget(self.groupBox_2)

        self.groupBox = QGroupBox(self.frame_2)
        self.groupBox.setObjectName("groupBox")
        self.groupBox.setMinimumSize(QSize(230, 70))
        self.groupBox.setMaximumSize(QSize(280, 70))
        self.groupBox.setFont(font4)
        self.verticalLayout_4 = QVBoxLayout(self.groupBox)
        self.verticalLayout_4.setSpacing(0)
        self.verticalLayout_4.setObjectName("verticalLayout_4")
        self.verticalLayout_4.setContentsMargins(-1, 0, -1, 0)
        self.horizontalLayout_10 = QHBoxLayout()
        self.horizontalLayout_10.setObjectName("horizontalLayout_10")
        self.horizontalLayout_10.setContentsMargins(10, 0, 10, 0)
        self.fit_linear = QRadioButton(self.groupBox)
        self.fit_linear.setObjectName("fit_linear")
        self.fit_linear.setChecked(True)

        self.horizontalLayout_10.addWidget(self.fit_linear, 0, Qt.AlignHCenter)

        self.fit_affinity = QRadioButton(self.groupBox)
        self.fit_affinity.setObjectName("fit_affinity")

        self.horizontalLayout_10.addWidget(self.fit_affinity, 0, Qt.AlignHCenter)

        self.verticalLayout_4.addLayout(self.horizontalLayout_10)

        self.chk_fitting_curve = QCheckBox(self.groupBox)
        self.chk_fitting_curve.setObjectName("chk_fitting_curve")
        sizePolicy.setHeightForWidth(
            self.chk_fitting_curve.sizePolicy().hasHeightForWidth()
        )
        self.chk_fitting_curve.setSizePolicy(sizePolicy)
        self.chk_fitting_curve.setMinimumSize(QSize(0, 0))
        self.chk_fitting_curve.setMaximumSize(QSize(200, 16777215))
        self.chk_fitting_curve.setFont(font4)
        self.chk_fitting_curve.setChecked(True)

        self.verticalLayout_4.addWidget(self.chk_fitting_curve, 0, Qt.AlignHCenter)

        self.horizontalLayout_8.addWidget(self.groupBox)

        self.horizontalSpacer_4 = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout_8.addItem(self.horizontalSpacer_4)

        self.results = QFrame(self.frame_2)
        self.results.setObjectName("results")
        self.results.setMinimumSize(QSize(460, 70))
        self.results.setMaximumSize(QSize(460, 70))
        self.results.setFrameShape(QFrame.StyledPanel)
        self.results.setFrameShadow(QFrame.Raised)
        self.affinity_result = QGroupBox(self.results)
        self.affinity_result.setObjectName("affinity_result")
        self.affinity_result.setEnabled(True)
        self.affinity_result.setGeometry(QRect(0, 0, 460, 70))
        self.affinity_result.setMinimumSize(QSize(460, 70))
        self.affinity_result.setMaximumSize(QSize(460, 70))
        self.affinity_result.setFont(font4)
        self.horizontalLayout_6 = QHBoxLayout(self.affinity_result)
        self.horizontalLayout_6.setObjectName("horizontalLayout_6")
        self.label_6 = QLabel(self.affinity_result)
        self.label_6.setObjectName("label_6")
        self.label_6.setMinimumSize(QSize(40, 0))
        font5 = QFont()
        font5.setBold(False)
        self.label_6.setFont(font5)
        self.label_6.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_6.addWidget(self.label_6)

        self.rmax_val = QLabel(self.affinity_result)
        self.rmax_val.setObjectName("rmax_val")
        self.rmax_val.setMinimumSize(QSize(60, 0))

        self.horizontalLayout_6.addWidget(self.rmax_val)

        self.label = QLabel(self.affinity_result)
        self.label.setObjectName("label")
        self.label.setMinimumSize(QSize(30, 0))
        self.label.setFont(font5)
        self.label.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_6.addWidget(self.label)

        self.kd_val = QLabel(self.affinity_result)
        self.kd_val.setObjectName("kd_val")
        self.kd_val.setMinimumSize(QSize(60, 0))

        self.horizontalLayout_6.addWidget(self.kd_val)

        self.label_3 = QLabel(self.affinity_result)
        self.label_3.setObjectName("label_3")
        self.label_3.setMinimumSize(QSize(30, 0))
        self.label_3.setFont(font5)
        self.label_3.setTextFormat(Qt.RichText)
        self.label_3.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_6.addWidget(self.label_3)

        self.chi_sq_val = QLabel(self.affinity_result)
        self.chi_sq_val.setObjectName("chi_sq_val")
        self.chi_sq_val.setMinimumSize(QSize(60, 0))

        self.horizontalLayout_6.addWidget(self.chi_sq_val)

        self.p_val = QLabel(self.affinity_result)
        self.p_val.setObjectName("p_val")

        self.horizontalLayout_6.addWidget(self.p_val)

        self.linear_result = QGroupBox(self.results)
        self.linear_result.setObjectName("linear_result")
        self.linear_result.setGeometry(QRect(0, 0, 460, 70))
        self.linear_result.setMinimumSize(QSize(460, 70))
        self.linear_result.setMaximumSize(QSize(460, 70))
        self.linear_result.setFont(font4)
        self.horizontalLayout_7 = QHBoxLayout(self.linear_result)
        self.horizontalLayout_7.setObjectName("horizontalLayout_7")
        self.horizontalLayout_7.setContentsMargins(-1, 7, -1, -1)
        self.label_4 = QLabel(self.linear_result)
        self.label_4.setObjectName("label_4")
        self.label_4.setMinimumSize(QSize(40, 0))
        self.label_4.setFont(font5)
        self.label_4.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_7.addWidget(self.label_4, 0, Qt.AlignRight)

        self.lin_eqn = QLabel(self.linear_result)
        self.lin_eqn.setObjectName("lin_eqn")
        self.lin_eqn.setMinimumSize(QSize(150, 0))

        self.horizontalLayout_7.addWidget(self.lin_eqn)

        self.label_5 = QLabel(self.linear_result)
        self.label_5.setObjectName("label_5")
        self.label_5.setMinimumSize(QSize(40, 0))
        self.label_5.setFont(font5)
        self.label_5.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_7.addWidget(self.label_5, 0, Qt.AlignRight)

        self.r_sq_val = QLabel(self.linear_result)
        self.r_sq_val.setObjectName("r_sq_val")
        self.r_sq_val.setMinimumSize(QSize(70, 0))
        self.r_sq_val.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_7.addWidget(self.r_sq_val)

        self.horizontalLayout_8.addWidget(self.results)

        self.frame = QFrame(self.frame_2)
        self.frame.setObjectName("frame")
        self.frame.setFont(font4)
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_2 = QHBoxLayout(self.frame)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.btn_save = QPushButton(self.frame)
        self.btn_save.setObjectName("btn_save")
        sizePolicy1 = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.btn_save.sizePolicy().hasHeightForWidth())
        self.btn_save.setSizePolicy(sizePolicy1)
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

        self.horizontalLayout_8.addWidget(self.frame)

        self.verticalLayout.addWidget(self.frame_2)

        self.retranslateUi(KDWizardDialog)

        self.btn_save.setDefault(False)

        QMetaObject.connectSlotsByName(KDWizardDialog)

    # setupUi

    def retranslateUi(self, KDWizardDialog):
        KDWizardDialog.setWindowTitle(
            QCoreApplication.translate("KDWizardDialog", "Fitting Wizard", None)
        )
        self.label_cur_info.setText("")
        ___qtablewidgetitem = self.table.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(
            QCoreApplication.translate("KDWizardDialog", "Cycle", None)
        )
        ___qtablewidgetitem1 = self.table.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(
            QCoreApplication.translate("KDWizardDialog", "Conc'n (nM)", None)
        )
        ___qtablewidgetitem2 = self.table.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(
            QCoreApplication.translate("KDWizardDialog", "Shift (RU)", None)
        )
        ___qtablewidgetitem3 = self.table.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(
            QCoreApplication.translate("KDWizardDialog", "Residual (RU)", None)
        )
        self.add_shifts.setText(
            QCoreApplication.translate(
                "KDWizardDialog", "Cumulative Shift Values", None
            )
        )
        self.btn_kd.setText(
            QCoreApplication.translate("KDWizardDialog", "Calculate KD", None)
        )
        self.groupBox_2.setTitle(
            QCoreApplication.translate("KDWizardDialog", "Channel", None)
        )
        self.ch_a.setText(QCoreApplication.translate("KDWizardDialog", "A", None))
        self.ch_b.setText(QCoreApplication.translate("KDWizardDialog", "B", None))
        self.ch_c.setText(QCoreApplication.translate("KDWizardDialog", "C", None))
        self.ch_d.setText(QCoreApplication.translate("KDWizardDialog", "D", None))
        self.groupBox.setTitle(
            QCoreApplication.translate("KDWizardDialog", "Fitting Model", None)
        )
        self.fit_linear.setText(
            QCoreApplication.translate("KDWizardDialog", "Linear", None)
        )
        self.fit_affinity.setText(
            QCoreApplication.translate("KDWizardDialog", "Affinity", None)
        )
        self.chk_fitting_curve.setText(
            QCoreApplication.translate("KDWizardDialog", "Plot Fitting Curve", None)
        )
        self.affinity_result.setTitle(
            QCoreApplication.translate("KDWizardDialog", "Affinity Result", None)
        )
        self.label_6.setText(
            QCoreApplication.translate(
                "KDWizardDialog",
                '<html><head/><body><p>R<span style=" vertical-align:sub;">MAX</span>:</p></body></html>',
                None,
            )
        )
        self.rmax_val.setText("")
        self.label.setText(QCoreApplication.translate("KDWizardDialog", "KD:", None))
        self.kd_val.setText("")
        self.label_3.setText(
            QCoreApplication.translate(
                "KDWizardDialog",
                '<html><head/><body><p>\u03c7<span style=" vertical-align:super;">2</span>:</p></body></html>',
                None,
            )
        )
        self.chi_sq_val.setText("")
        self.p_val.setText(QCoreApplication.translate("KDWizardDialog", "p:", None))
        self.linear_result.setTitle(
            QCoreApplication.translate("KDWizardDialog", "Linear Result", None)
        )
        self.label_4.setText(QCoreApplication.translate("KDWizardDialog", "Y = ", None))
        self.lin_eqn.setText("")
        self.label_5.setText(
            QCoreApplication.translate(
                "KDWizardDialog",
                '<html><head/><body><p>R<span style=" vertical-align:super;">2</span>:</p></body></html>',
                None,
            )
        )
        self.r_sq_val.setText("")
        # if QT_CONFIG(tooltip)
        self.btn_save.setToolTip(
            QCoreApplication.translate("KDWizardDialog", "Export Segment Data", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.btn_save.setText("")

    # retranslateUi
